#!/usr/bin/env python3
"""Real-time 3D Gazebo Marker Overlay + Tactical Mission Control HUD for live demos.

Makes spoofing provenance, timing, divergence, and AI Guardian cutover visually explicit:
  1. Publishes live 3D markers directly into Gazebo Sim (/marker service + /marker_array):
     - Cyan planned 12x12 m flight square
     - Blue real quadrotor trail
     - Red Spoofer Ground TX RF beam -> drone + Red "SPOOFED GPS BELIEF" Ghost sphere
     - Emerald Green "AI GUARDIAN HOLD" shield ring when GPS-denied failover engages
  2. Displays a side-by-side Tactical HUD window (unless --no-window) showing:
     - 2D radar map with TX RF pulse rings, Real vs EKF vs Spoofed Ghost tracks
     - Live AI Spoof Probability P(spoof) & Hijack Divergence time-series plots
     - Clear status banner, sensor mode pills (GPS / Optical Flow / LiDAR / Mode),
       and plain-English chronological event log explaining why failsafe triggered.
"""

import argparse
from collections import deque
import json
import math
import os
import sys
import time
from typing import Deque, List, Optional, Tuple

import cv2
import numpy as np
from gz.msgs10.boolean_pb2 import Boolean
from gz.msgs10.marker_pb2 import Marker
from gz.msgs10.marker_v_pb2 import Marker_V
from gz.transport13 import Node as GzNode
from nav_msgs.msg import Odometry
from px4_msgs.msg import (
    EstimatorStatusFlags,
    SensorGps,
    VehicleLocalPosition,
    VehicleStatus,
)
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String

from gps_failsafe_pkg.feature_extractor import gps_to_local_ned
from gps_failsafe_pkg.qos_profiles import px4_sub_qos


# Rogue ground transmitter coordinates in Gazebo ENU (x=East, y=North, z=Up)
TX_GZ_ENU = (-8.0, 8.0, 3.15)
TX_NED = (8.0, -8.0)  # (N, E)

NAV_NAMES = {
    2: "POSCTL",
    4: "HOLD (AUTO.LOITER)",
    14: "OFFBOARD",
    18: "AUTO.LAND",
}


class DemoHudNode(Node):
    """Drives live Gazebo 3D markers and a real-time 2D Tactical Telemetry HUD."""

    def __init__(self, show_window: bool = True, square_size: float = 12.0, alt_m: float = 4.0) -> None:
        super().__init__("demo_hud_node")
        self.show_window = bool(show_window)
        self.half_sq = float(square_size) / 2.0
        self.alt_m = float(alt_m)

        self._t0_s = time.monotonic()
        self._lpos: Optional[VehicleLocalPosition] = None
        self._gps: Optional[SensorGps] = None
        self._gt: Optional[Odometry] = None
        self._flags: Optional[EstimatorStatusFlags] = None
        self._vstatus: Optional[VehicleStatus] = None
        self._mission: Optional[dict] = None
        self._guardian: Optional[dict] = None
        self._adv: Optional[dict] = None
        self._adv_last_s = 0.0

        self._gt_trail: Deque[Tuple[float, float, float]] = deque(maxlen=400)  # (N, E, D)
        self._est_trail: Deque[Tuple[float, float]] = deque(maxlen=400)
        self._gps_trail: Deque[Tuple[float, float]] = deque(maxlen=400)
        self._hist_t: Deque[float] = deque(maxlen=240)
        self._hist_prob: Deque[float] = deque(maxlen=240)
        self._hist_err: Deque[float] = deque(maxlen=240)
        self._hist_gres: Deque[float] = deque(maxlen=240)

        self._events: Deque[Tuple[str, Tuple[int, int, int]]] = deque(maxlen=6)
        self._saw_takeoff = False
        self._saw_spoof = False
        self._saw_failover = False
        self._last_wp_logged = -1
        self._spoof_start_s: Optional[float] = None
        self._failover_start_s: Optional[float] = None
        self._pulse_phase = 0.0
        self._events.append(("[T+0.0s] System online: waiting for drone takeoff...", (190, 210, 220)))

        # Gazebo transport marker service client (/marker_array on GUI MarkerManager plugin)
        self._gz = GzNode()
        self._static_markers_sent = False

        # Subscriptions
        sub_q = px4_sub_qos()
        self.create_subscription(VehicleLocalPosition, "/fmu/out/vehicle_local_position", lambda m: setattr(self, "_lpos", m), sub_q)
        self.create_subscription(SensorGps, "/fmu/out/vehicle_gps_position", lambda m: setattr(self, "_gps", m), sub_q)
        self.create_subscription(EstimatorStatusFlags, "/fmu/out/estimator_status_flags", lambda m: setattr(self, "_flags", m), sub_q)
        self.create_subscription(VehicleStatus, "/fmu/out/vehicle_status", lambda m: setattr(self, "_vstatus", m), sub_q)
        self.create_subscription(Odometry, "/uav/ground_truth_odom", lambda m: setattr(self, "_gt", m), 10)
        self.create_subscription(String, "/mission/status", self._on_mission, 10)
        self.create_subscription(String, "/guardian/status", self._on_guardian, 10)
        self.create_subscription(String, "/adversary/attack_status", self._on_adv, 10)

        # Optional Tkinter HUD window backed by fast OpenCV raster
        self._tk_root = None
        self._tk_label = None
        self._tk_img = None
        if self.show_window and os.environ.get("DISPLAY"):
            try:
                import tkinter as tk

                self._tk_root = tk.Tk()
                self._tk_root.title("UAV GPS-Failsafe | Tactical Cyber-Attack & AI Guardian HUD")
                self._tk_root.geometry("820x820+1220+40")
                self._tk_root.resizable(False, False)
                self._tk_root.configure(bg="#181412")
                self._tk_label = tk.Label(self._tk_root, bg="#181412", bd=0, highlightthickness=0)
                self._tk_label.pack()
                self._tk_root.update_idletasks()
                self._tk_root.update()
            except Exception as exc:
                self.get_logger().warn(f"HUD window disabled ({exc}); running 3D Gazebo markers only.")
                self._tk_root = None

        self.create_timer(0.1, self._tick)  # 10 Hz HUD & Gazebo 3D marker updates
        self.get_logger().info(f"Demo HUD node started (window={self._tk_root is not None})")

    def _on_mission(self, msg: String) -> None:
        try:
            self._mission = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def _on_guardian(self, msg: String) -> None:
        try:
            self._guardian = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def _on_adv(self, msg: String) -> None:
        try:
            self._adv = json.loads(msg.data)
            self._adv_last_s = time.monotonic()
        except json.JSONDecodeError:
            pass

    @staticmethod
    def _make_marker(
        mid: int,
        ns: str,
        mtype: int,
        action: int,
        rgba: Tuple[float, float, float, float],
        scale: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        pos: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        pts: Optional[List[Tuple[float, float, float]]] = None,
        text: str = "",
    ) -> Marker:
        m = Marker()
        m.id = mid
        m.ns = ns
        m.type = mtype
        m.action = action
        m.pose.position.x, m.pose.position.y, m.pose.position.z = float(pos[0]), float(pos[1]), float(pos[2])
        m.pose.orientation.w = 1.0
        m.scale.x, m.scale.y, m.scale.z = float(scale[0]), float(scale[1]), float(scale[2])
        m.material.ambient.r, m.material.ambient.g, m.material.ambient.b, m.material.ambient.a = rgba
        m.material.diffuse.r, m.material.diffuse.g, m.material.diffuse.b, m.material.diffuse.a = rgba
        m.material.emissive.r, m.material.emissive.g, m.material.emissive.b, m.material.emissive.a = rgba
        if pts:
            for px, py, pz in pts:
                p = m.point.add()
                p.x, p.y, p.z = float(px), float(py), float(pz)
        if text:
            m.text = text
        return m

    def _publish_gz_markers(
        self,
        gt_ned: Tuple[float, float, float],
        gps_ned: Optional[Tuple[float, float, float]],
        spoof_active: bool,
        failover_active: bool,
    ) -> None:
        mv = Marker_V()
        h = self.half_sq
        alt = self.alt_m

        # 1. Planned 12x12m square mission corridor at flight altitude
        sending_static = not self._static_markers_sent
        if sending_static:
            sq_pts = [(-h, h, alt), (h, h, alt), (h, -h, alt), (-h, -h, alt), (-h, h, alt)]
            mv.marker.append(
                self._make_marker(
                    10, "mission", Marker.LINE_STRIP, Marker.ADD_MODIFY,
                    (0.15, 0.92, 0.72, 0.78), pts=sq_pts,
                )
            )

        # 2. Real physical drone trail in bright Gold/Amber (ENU x=E, y=N, z=-D)
        if len(self._gt_trail) >= 2:
            trail_pts = [(e, n, max(0.2, -d)) for n, e, d in self._gt_trail]
            mv.marker.append(
                self._make_marker(
                    11, "gt_trail", Marker.LINE_STRIP, Marker.ADD_MODIFY,
                    (1.0, 0.82, 0.12, 1.0), pts=trail_pts,
                )
            )

        gt_gz = (gt_ned[1], gt_ned[0], max(0.2, -gt_ned[2]))

        # 3. Active Spoofer TX pulse + RF beam + Spoofed GPS Ghost + Spoofed trail
        if spoof_active and gps_ned is not None:
            pulse_d = 0.45 + 0.75 * self._pulse_phase
            mv.marker.append(
                self._make_marker(
                    12, "tx_pulse", Marker.SPHERE, Marker.ADD_MODIFY,
                    (1.0, 0.15, 0.10, max(0.15, 0.65 * (1.0 - self._pulse_phase))),
                    scale=(pulse_d, pulse_d, pulse_d),
                    pos=TX_GZ_ENU,
                )
            )
            gps_gz = (gps_ned[1], gps_ned[0], max(0.3, -gt_ned[2]))
            mv.marker.append(
                self._make_marker(
                    13, "spoof_beam", Marker.LINE_LIST, Marker.ADD_MODIFY,
                    (1.0, 0.12, 0.10, 0.98),
                    pts=[TX_GZ_ENU, gt_gz, gt_gz, gps_gz],
                )
            )
            mv.marker.append(
                self._make_marker(
                    14, "spoof_ghost", Marker.SPHERE, Marker.ADD_MODIFY,
                    (1.0, 0.18, 0.12, 0.72), scale=(0.85, 0.85, 0.45), pos=gps_gz,
                )
            )
            if len(self._gps_trail) >= 2:
                gpts = [(e, n, alt + 0.06) for n, e in self._gps_trail]
                mv.marker.append(
                    self._make_marker(
                        19, "gps_trail", Marker.LINE_STRIP, Marker.ADD_MODIFY,
                        (1.0, 0.18, 0.15, 0.88), pts=gpts,
                    )
                )
        else:
            for del_id, ns in ((12, "tx_pulse"), (13, "spoof_beam"), (14, "spoof_ghost"), (19, "gps_trail")):
                mv.marker.append(self._make_marker(del_id, ns, Marker.SPHERE, Marker.DELETE_MARKER, (0, 0, 0, 0)))

        # 4. Emerald Guardian Hover Shield around real drone once failover locks
        if failover_active:
            mv.marker.append(
                self._make_marker(
                    16, "guardian_shield", Marker.CYLINDER, Marker.ADD_MODIFY,
                    (0.10, 0.98, 0.45, 0.45), scale=(1.75, 1.75, 0.30), pos=gt_gz,
                )
            )
        else:
            mv.marker.append(self._make_marker(16, "guardian_shield", Marker.CYLINDER, Marker.DELETE_MARKER, (0, 0, 0, 0)))

        if len(mv.marker) > 0:
            try:
                ok, _ = self._gz.request("/marker_array", mv, Marker_V, Boolean, 60)
                if ok and sending_static:
                    self._static_markers_sent = True
            except Exception:
                pass

    def _render_hud(
        self,
        elapsed_s: float,
        gt_ned: Tuple[float, float, float],
        est_ned: Tuple[float, float, float],
        gps_ned: Optional[Tuple[float, float, float]],
        spoof_active: bool,
        adv_mode: str,
        adv_desc: str,
        failover_active: bool,
        prob: float,
    ) -> None:
        if self._tk_root is None:
            return

        W, H = 820, 820
        canvas = np.full((H, W, 3), (24, 20, 18), dtype=np.uint8)  # BGR dark slate

        # --- Top Banner (Explains state at a glance) ---
        has_guardian = self._guardian is not None
        if failover_active:
            b_col, txt_col = (40, 130, 35), (240, 255, 240)
            since_s = f"@{self._spoof_start_s:.1f}s" if self._spoof_start_s else ""
            banner = f"AI GUARDIAN INTERCEPTED SPOOF {since_s} (P={prob:.2f}) -> GPS CUT -> SAFE HOVER"
        elif spoof_active and not has_guardian:
            b_col, txt_col = (35, 35, 200), (255, 245, 245)
            banner = f"UNPROTECTED SPOOF FROM TX (-8,+8): DRONE TRAJECTORY HIJACKED | {adv_desc}"
        elif spoof_active:
            b_col, txt_col = (35, 35, 195), (255, 245, 245)
            banner = f"ALERT: SPOOF SIGNAL FROM TX (-8,+8) | {adv_desc} | P(spoof)={prob:.2f}"
        elif self._mission and self._mission.get("phase") == "MISSION":
            wp_i = int(self._mission.get("wp_index", 0))
            b_col, txt_col = (120, 80, 25), (245, 250, 255)
            banner = f"NOMINAL AUTONOMOUS SQUARE (WP {wp_i}/4) | GPS + Optical Flow + LiDAR"
        else:
            b_col, txt_col = (60, 60, 65), (225, 230, 235)
            banner = "PRE-FLIGHT / TAKEOFF  |  Arming & climbing to 4.0 m mission altitude"

        cv2.rectangle(canvas, (10, 10), (W - 10, 56), b_col, -1)
        cv2.putText(canvas, banner, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.53, txt_col, 2, cv2.LINE_AA)

        # --- Left Panel: Tactical 2D Map (-16m .. +16m) ---
        mx0, my0, msz = 18, 72, 460
        cv2.rectangle(canvas, (mx0, my0), (mx0 + msz, my0 + msz), (34, 30, 28), -1)
        cv2.rectangle(canvas, (mx0, my0), (mx0 + msz, my0 + msz), (80, 80, 88), 1)
        scale = msz / 34.0  # covers [-17 .. +17] m in E and N

        def ned_to_px(n: float, e: float) -> Tuple[int, int]:
            px = int(np.clip(mx0 + msz / 2 + e * scale, mx0 + 4, mx0 + msz - 4))
            py = int(np.clip(my0 + msz / 2 - n * scale, my0 + 4, my0 + msz - 4))
            return px, py

        # Grid every 5m
        for gval in range(-15, 16, 5):
            gx0, _ = ned_to_px(0.0, gval)
            _, gy0 = ned_to_px(gval, 0.0)
            col = (65, 65, 72) if gval == 0 else (45, 44, 48)
            cv2.line(canvas, (gx0, my0), (gx0, my0 + msz), col, 1)
            cv2.line(canvas, (mx0, gy0), (mx0 + msz, gy0), col, 1)

        # Helipad & planned square + 4 labeled corners (matching mission_runner_node square order)
        hx, hy = ned_to_px(0.0, 0.0)
        cv2.circle(canvas, (hx, hy), 9, (40, 180, 230), 2)
        h = self.half_sq
        p1, p2 = ned_to_px(h, -h), ned_to_px(-h, h)
        cv2.rectangle(canvas, p1, p2, (95, 185, 120), 2)
        cur_wp = int(self._mission.get("wp_index", -1)) if self._mission else -1
        corners = [
            (1, h, -h, "WP1 TOP-LEFT", -36, -12),
            (2, h, h, "WP2 TOP-RIGHT", -68, -12),
            (3, -h, h, "WP3 BOT-RIGHT", -68, 22),
            (4, -h, -h, "WP4 BOT-LEFT", -36, 22),
        ]
        for idx, cn, ce, clabel, dx, dy in corners:
            cx, cy_c = ned_to_px(cn, ce)
            is_tgt = idx == cur_wp
            cc = (60, 220, 255) if is_tgt else (110, 195, 130)
            cv2.circle(canvas, (cx, cy_c), 7 if is_tgt else 5, cc, -1 if is_tgt else 2)
            cv2.putText(canvas, clabel, (cx + dx, cy_c + dy), cv2.FONT_HERSHEY_SIMPLEX, 0.36, cc, 1, cv2.LINE_AA)

        # Rogue Spoofer TX (-8, +8 -> N=+8, E=-8)
        tx_px = ned_to_px(TX_NED[0], TX_NED[1])
        cv2.rectangle(canvas, (tx_px[0] - 8, tx_px[1] - 8), (tx_px[0] + 8, tx_px[1] + 8), (60, 60, 230), -1)
        cv2.putText(canvas, "Spoofer TX (-8,+8)", (tx_px[0] - 46, tx_px[1] - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.39, (110, 110, 255), 1, cv2.LINE_AA)

        # Animated RF rings + beam when Spoofer active
        gt_px = ned_to_px(gt_ned[0], gt_ned[1])
        if spoof_active:
            for ring_i in range(3):
                rad = int(((self._pulse_phase + ring_i * 0.33) % 1.0) * 58) + 8
                cv2.circle(canvas, tx_px, rad, (60, 60, 220), 1, cv2.LINE_AA)
            cv2.line(canvas, tx_px, gt_px, (70, 70, 240), 1, cv2.LINE_AA)

        # Trails
        if len(self._gps_trail) >= 2:
            pts = np.array([ned_to_px(n, e) for n, e in self._gps_trail], dtype=np.int32)
            cv2.polylines(canvas, [pts], False, (80, 110, 255), 1, cv2.LINE_AA)
        if len(self._gt_trail) >= 2:
            pts = np.array([ned_to_px(n, e) for n, e, _ in self._gt_trail], dtype=np.int32)
            cv2.polylines(canvas, [pts], False, (255, 185, 45), 2, cv2.LINE_AA)

        # Spoofed GPS phantom marker + divergence arrow
        if gps_ned is not None:
            g_px = ned_to_px(gps_ned[0], gps_ned[1])
            if spoof_active:
                cv2.arrowedLine(canvas, gt_px, g_px, (60, 70, 255), 2, cv2.LINE_AA, tipLength=0.22)
                cv2.circle(canvas, g_px, 8, (60, 60, 255), 2)
                cv2.putText(canvas, "SPOOFED GPS", (g_px[0] + 10, g_px[1] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (90, 90, 255), 1, cv2.LINE_AA)
            else:
                cv2.circle(canvas, g_px, 4, (80, 220, 120), 1)

        # EKF2 Belief & Real Drone
        est_px = ned_to_px(est_ned[0], est_ned[1])
        cv2.drawMarker(canvas, est_px, (240, 240, 240), cv2.MARKER_CROSS, 12, 1)
        cv2.circle(canvas, gt_px, 6, (255, 200, 40), -1)
        if failover_active:
            cv2.circle(canvas, gt_px, 16, (70, 235, 110), 2, cv2.LINE_AA)
            cv2.putText(canvas, "HOLD LOCK", (gt_px[0] + 14, gt_px[1] + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (80, 245, 120), 1, cv2.LINE_AA)

        # Map legend footer
        cv2.putText(canvas, "Tactical Map (34x34m): Cyan=Real UAV  White+=EKF2  Red=Spoofed GPS", (mx0 + 6, my0 + msz - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (185, 190, 195), 1, cv2.LINE_AA)

        # --- Right Panel: Sensor Status Pills + Rolling Telemetry Plots ---
        rx0, rw = mx0 + msz + 14, W - (mx0 + msz + 24)
        fl = self._flags
        vs = self._vstatus
        cs_gps = bool(fl.cs_gps) if fl else True
        cs_of = bool(fl.cs_opt_flow) if fl else False
        cs_rng = bool(fl.cs_rng_hgt) if fl else False
        nav = int(vs.nav_state) if vs else 0
        nav_str = NAV_NAMES.get(nav, f"MODE_{nav}")

        cards = [
            ("FLIGHT MODE", nav_str, (60, 175, 80) if nav == 4 and failover_active else (180, 130, 40)),
            ("EKF2 GPS FUSION", "ISOLATED (GPS_CTRL=0)" if not cs_gps else ("SPOOFED!" if spoof_active else "ACTIVE (GPS_CTRL=7)"), (40, 165, 70) if not cs_gps else ((45, 45, 210) if spoof_active else (55, 130, 60))),
            ("OPTICAL FLOW", "PRIMARY AIDING" if (not cs_gps and cs_of) else ("ACTIVE" if cs_of else "OFF"), (200, 160, 35) if cs_of else (60, 60, 160)),
            ("1D LiDAR HEIGHT", "PRIMARY REF (HGT=2)" if (failover_active and cs_rng) else ("ACTIVE" if cs_rng else "OFF"), (200, 160, 35) if cs_rng else (60, 60, 160)),
        ]
        cy = my0
        for label, val, ccol in cards:
            cv2.rectangle(canvas, (rx0, cy), (rx0 + rw, cy + 44), (38, 35, 34), -1)
            cv2.rectangle(canvas, (rx0, cy), (rx0 + 6, cy + 44), ccol, -1)
            cv2.putText(canvas, label, (rx0 + 14, cy + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (165, 170, 180), 1, cv2.LINE_AA)
            cv2.putText(canvas, val, (rx0 + 14, cy + 36), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (240, 245, 250), 1, cv2.LINE_AA)
            cy += 52

        # Plot 1: AI Guardian Spoof Probability P(spoof)
        py1, ph1 = cy + 6, 112
        cv2.rectangle(canvas, (rx0, py1), (rx0 + rw, py1 + ph1), (34, 30, 28), -1)
        p1_title = (
            f"AI Spoof Probability P={prob:.3f} (thresh=0.80)"
            if self._guardian is not None
            else "AI Guardian: DISABLED (UNPROTECTED FLIGHT)"
        )
        cv2.putText(canvas, p1_title, (rx0 + 8, py1 + 17), cv2.FONT_HERSHEY_SIMPLEX, 0.41, (215, 220, 225) if self._guardian is not None else (110, 110, 240), 1, cv2.LINE_AA)
        th_y = int(py1 + ph1 - 10 - 0.80 * (ph1 - 30))
        cv2.line(canvas, (rx0 + 6, th_y), (rx0 + rw - 6, th_y), (65, 65, 210), 1)
        if len(self._hist_prob) >= 2:
            probs = list(self._hist_prob)
            xs = np.linspace(rx0 + 6, rx0 + rw - 6, len(probs)).astype(int)
            ys = [int(py1 + ph1 - 10 - np.clip(p, 0.0, 1.0) * (ph1 - 30)) for p in probs]
            cv2.polylines(canvas, [np.column_stack([xs, ys])], False, (70, 220, 255), 2, cv2.LINE_AA)

        # Plot 2: Hijack Error ||Est - GT|| vs GPS Divergence
        py2, ph2 = py1 + ph1 + 12, 122
        cur_err = self._hist_err[-1] if self._hist_err else 0.0
        cur_res = self._hist_gres[-1] if self._hist_gres else 0.0
        cv2.rectangle(canvas, (rx0, py2), (rx0 + rw, py2 + ph2), (34, 30, 28), -1)
        cv2.putText(canvas, f"Hijack={cur_err:.2f}m (Cyan) | GPS Res={cur_res:.2f}m (Red)", (rx0 + 8, py2 + 17), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (215, 220, 225), 1, cv2.LINE_AA)
        if len(self._hist_err) >= 2:
            max_y = max(5.0, float(max(max(self._hist_err), max(self._hist_gres))))
            xs = np.linspace(rx0 + 6, rx0 + rw - 6, len(self._hist_err)).astype(int)
            ys_res = [int(py2 + ph2 - 10 - np.clip(v / max_y, 0.0, 1.0) * (ph2 - 30)) for v in self._hist_gres]
            ys_err = [int(py2 + ph2 - 10 - np.clip(v / max_y, 0.0, 1.0) * (ph2 - 30)) for v in self._hist_err]
            cv2.polylines(canvas, [np.column_stack([xs, ys_res])], False, (80, 90, 250), 1, cv2.LINE_AA)
            cv2.polylines(canvas, [np.column_stack([xs, ys_err])], False, (255, 200, 45), 2, cv2.LINE_AA)

        # --- Bottom Panel: Plain-English Event Timeline Explaining What/When/Why ---
        ey0 = my0 + msz + 14
        cv2.rectangle(canvas, (18, ey0), (W - 10, H - 12), (32, 29, 28), -1)
        cv2.rectangle(canvas, (18, ey0), (W - 10, H - 12), (75, 75, 85), 1)
        cv2.putText(canvas, "REAL-TIME DECISION & EVENT LOG (WHY & WHEN ACTIONS OCCUR)", (30, ey0 + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (215, 225, 235), 1, cv2.LINE_AA)
        line_y = ey0 + 52
        for text, col in self._events:
            cv2.putText(canvas, text, (30, line_y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, col, 1, cv2.LINE_AA)
            line_y += 32

        # Push BGR -> RGB PPM photo to Tkinter
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        ppm = f"P6\n{W} {H}\n255\n".encode("ascii") + rgb.tobytes()
        try:
            import tkinter as tk

            self._tk_img = tk.PhotoImage(data=ppm)
            self._tk_label.configure(image=self._tk_img)
            self._tk_root.update_idletasks()
            self._tk_root.update()
        except Exception:
            self._tk_root = None

    def _tick(self) -> None:
        if self._lpos is None or self._gt is None:
            return
        now = time.monotonic()
        elapsed_s = now - self._t0_s
        self._pulse_phase = (self._pulse_phase + 0.08) % 1.0

        gp = self._gt.pose.pose.position
        gt_ned = (float(gp.x), float(gp.y), float(gp.z))
        est_ned = (float(self._lpos.x), float(self._lpos.y), float(self._lpos.z))
        self._gt_trail.append(gt_ned)
        self._est_trail.append((est_ned[0], est_ned[1]))

        gps_ned: Optional[Tuple[float, float, float]] = None
        gps_res = 0.0
        if self._gps is not None and abs(self._lpos.ref_lat) > 1e-3:
            gps_ned = gps_to_local_ned(
                self._gps.latitude_deg,
                self._gps.longitude_deg,
                self._gps.altitude_msl_m,
                self._lpos.ref_lat,
                self._lpos.ref_lon,
                self._lpos.ref_alt,
            )
            self._gps_trail.append((gps_ned[0], gps_ned[1]))
            gps_res = math.hypot(gps_ned[0] - est_ned[0], gps_ned[1] - est_ned[1])

        hijack_err = math.hypot(est_ned[0] - gt_ned[0], est_ned[1] - gt_ned[1])

        adv = self._adv if (self._adv and (now - self._adv_last_s) < 1.2) else None
        spoof_active = bool(adv and adv.get("active"))
        adv_mode = str(adv.get("mode", "none")) if spoof_active else "none"
        adv_rate = float(adv.get("rate_mps", 0.0)) if spoof_active else 0.0
        adv_off = adv.get("offset_ned", [0.0, 0.0, 0.0]) if spoof_active else [0.0, 0.0, 0.0]
        adv_desc = (
            f"STEP ({adv_off[0]:.1f}m N, {adv_off[1]:.1f}m E)"
            if adv_mode == "step"
            else f"{adv_mode.upper()} @ {adv_rate:.1f} m/s (offset={math.hypot(adv_off[0], adv_off[1]):.1f}m)"
        )

        g = self._guardian or {}
        failover_active = bool(g.get("failover_active", False))
        prob = float(g.get("spoof_prob", 0.0))

        self._hist_t.append(elapsed_s)
        self._hist_prob.append(prob)
        self._hist_err.append(hijack_err)
        self._hist_gres.append(gps_res)

        wp_names = {1: "Top-Left", 2: "Top-Right", 3: "Bottom-Right", 4: "Bottom-Left", 5: "Center"}
        if self._mission and self._mission.get("phase") == "MISSION":
            wp_idx = int(self._mission.get("wp_index", 0))
            if not self._saw_takeoff:
                self._saw_takeoff = True
                self._events.append((f"[T+{elapsed_s:.1f}s] Takeoff complete: starting defined 12x12m square mission.", (140, 235, 175)))
            if wp_idx != self._last_wp_logged and wp_idx in wp_names:
                self._last_wp_logged = wp_idx
                if wp_idx == 4:
                    self._events.append((f"[T+{elapsed_s:.1f}s] Passed Top-Left -> Top-Right -> Bot-Right; heading to Bot-Left...", (190, 225, 245)))
                elif wp_idx == 1:
                    self._events.append((f"[T+{elapsed_s:.1f}s] Navigating defined leg 1 -> WP1 Top-Left (+6, -6).", (175, 215, 230)))
        if not self._saw_spoof and spoof_active:
            self._saw_spoof = True
            self._spoof_start_s = elapsed_s
            self._events.append((f"[T+{elapsed_s:.1f}s] SPOOF SIGNAL ARRIVED from TX (-8,+8): {adv_desc}!", (90, 95, 255)))
        if not self._saw_failover and failover_active:
            self._saw_failover = True
            self._failover_start_s = elapsed_s
            exec_ms = g.get("failover_exec_ms") or 0.0
            self._events.append((f"[T+{elapsed_s:.1f}s] AI GUARDIAN (P={prob:.3f}): GPS-vs-OF/IMU divergence -> CUT GPS ({exec_ms:.1f}ms)!", (80, 245, 120)))
            self._events.append((f"[T+{elapsed_s:.1f}s] PX4 switched to HOLD (AUTO.LOITER) on Optical Flow + 1D LiDAR -> SAFE HOVER.", (255, 220, 110)))

        self._publish_gz_markers(gt_ned, gps_ned, spoof_active, failover_active)
        self._render_hud(elapsed_s, gt_ned, est_ned, gps_ned, spoof_active, adv_mode, adv_desc, failover_active, prob)

    def shutdown(self) -> None:
        if self._tk_root is not None:
            try:
                self._tk_root.destroy()
            except Exception:
                pass


def parse_cli_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live Gazebo 3D Marker & Tactical HUD Visualizer")
    parser.add_argument("--no-window", action="store_true", help="Disable Tkinter HUD window (headless markers only)")
    parser.add_argument("--square-size", type=float, default=12.0)
    parser.add_argument("--altitude", type=float, default=4.0)
    known, _ = parser.parse_known_args(argv)
    return known


def main(args=None) -> None:
    cli = parse_cli_args(sys.argv[1:])
    rclpy.init(args=args)
    node = DemoHudNode(show_window=not cli.no_window, square_size=cli.square_size, alt_m=cli.altitude)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception:
        if rclpy.ok():
            raise
    finally:
        node.shutdown()
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

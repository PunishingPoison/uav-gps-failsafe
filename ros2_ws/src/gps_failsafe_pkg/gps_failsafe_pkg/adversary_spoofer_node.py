#!/usr/bin/env python3
"""Adversary GPS spoofer node supporting Step, Drift, and Coordinated Takeover attacks.

Preempts sensor_bridge_node's nominal HIL_GPS feed by asserting /adversary/active = True
and directly transmitting manipulated MAVLink HIL_GPS packets to PX4 while logging exact
ground-truth attack offsets and t_attack_start metadata on /adversary/attack_status.
"""

import argparse
import json
import math
import sys
import time
from typing import Optional

import numpy as np
from pymavlink import mavutil
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from nav_msgs.msg import Odometry
from sensor_msgs.msg import NavSatFix
from std_msgs.msg import Bool, String


EARTH_RADIUS_M = 6_371_000.0


class AdversarySpooferNode(Node):
    """Injects configurable GPS spoofing profiles into PX4 SITL via HIL_GPS."""

    def __init__(
        self,
        mode: str = "drift",
        rate_mps: float = 2.0,
        bearing_deg: float = 0.0,
        offset_n: float = 15.0,
        offset_e: float = 0.0,
        offset_d: float = 0.0,
        delay_s: float = 0.0,
        duration_s: float = 0.0,
        ramp_s: float = 2.5,
        mavlink_url: str = "udpout:127.0.0.1:13030",
    ) -> None:
        super().__init__("adversary_spoofer_node")

        self.mode = mode
        self.rate_mps = float(rate_mps)
        self.bearing_rad = math.radians(float(bearing_deg))
        self.bearing_deg = float(bearing_deg)
        self.step_offset_ned = np.array([offset_n, offset_e, offset_d], dtype=np.float64)
        self.delay_s = max(0.0, float(delay_s))
        self.duration_s = float(duration_s)
        self.ramp_s = max(0.2, float(ramp_s))

        self.mav = mavutil.mavlink_connection(mavlink_url, source_system=1, source_component=191)
        self._rng = np.random.default_rng(777)
        self._boot_wall_ns = time.monotonic_ns()
        self._node_start_s = time.monotonic()

        self._latest_navsat: Optional[NavSatFix] = None
        self._latest_odom: Optional[Odometry] = None

        self._attack_active = False
        self._t_attack_start_s: Optional[float] = None
        self._t_attack_start_ns: Optional[int] = None
        self._prev_tick_s: Optional[float] = None
        self._spoof_pos_ned = np.zeros(3, dtype=np.float64)
        self._spoof_vel_ned = np.zeros(3, dtype=np.float64)

        self.create_subscription(NavSatFix, "/uav/ground_truth_navsat", self._on_navsat, 10)
        self.create_subscription(Odometry, "/uav/ground_truth_odom", self._on_odom, 10)

        self.active_pub = self.create_publisher(Bool, "/adversary/active", 10)
        self.status_pub = self.create_publisher(String, "/adversary/attack_status", 10)

        self.create_timer(0.1, self._tick)  # 10 Hz HIL_GPS rate
        self.get_logger().info(
            f"Adversary ready: mode={self.mode}, rate={self.rate_mps}m/s, "
            f"bearing={self.bearing_deg}deg, delay={self.delay_s}s, mav={mavlink_url}"
        )

    def _on_navsat(self, msg: NavSatFix) -> None:
        self._latest_navsat = msg

    def _on_odom(self, msg: Odometry) -> None:
        self._latest_odom = msg

    def _compute_spoof_offset(self, now_s: float) -> None:
        if self._t_attack_start_s is None:
            self._t_attack_start_s = now_s
            self._t_attack_start_ns = self.get_clock().now().nanoseconds
            self._prev_tick_s = now_s
            self._spoof_pos_ned[:] = 0.0
            self._spoof_vel_ned[:] = 0.0

        dt = max(0.0, now_s - (self._prev_tick_s or now_s))
        self._prev_tick_s = now_s
        elapsed = now_s - self._t_attack_start_s

        dir_n = math.cos(self.bearing_rad)
        dir_e = math.sin(self.bearing_rad)

        if self.mode == "step":
            self._spoof_pos_ned = self.step_offset_ned.copy()
            # Keep velocity realistic or brief transient so EKF2 snaps cleanly
            self._spoof_vel_ned[:] = 0.0

        elif self.mode == "drift":
            # Linear meaconing / ramp drift in GPS position + subtle velocity bias
            self._spoof_pos_ned[0] = self.rate_mps * elapsed * dir_n
            self._spoof_pos_ned[1] = self.rate_mps * elapsed * dir_e
            self._spoof_pos_ned[2] = 0.0
            self._spoof_vel_ned[0] = 0.5 * self.rate_mps * dir_n
            self._spoof_vel_ned[1] = 0.5 * self.rate_mps * dir_e
            self._spoof_vel_ned[2] = 0.0

        elif self.mode == "takeover":
            # Smooth S-curve velocity ramp + coherent integrated position offset
            # to slip past EKF2 innovation gates and fully hijack position control
            alpha = min(1.0, elapsed / self.ramp_s)
            smooth = 0.5 * (1.0 - math.cos(math.pi * alpha))
            v_bias_n = self.rate_mps * smooth * dir_n
            v_bias_e = self.rate_mps * smooth * dir_e
            self._spoof_vel_ned = np.array([v_bias_n, v_bias_e, 0.0], dtype=np.float64)
            self._spoof_pos_ned[0] += v_bias_n * dt
            self._spoof_pos_ned[1] += v_bias_e * dt
            self._spoof_pos_ned[2] = 0.0

    def _publish_active(self, active: bool) -> None:
        msg = Bool()
        msg.data = active
        self.active_pub.publish(msg)

    def _tick(self) -> None:
        now_s = time.monotonic()
        since_launch = now_s - self._node_start_s

        if since_launch < self.delay_s:
            self._publish_active(False)
            self._publish_status(False, None, None, None)
            return

        if self.duration_s > 0.0 and self._t_attack_start_s is not None:
            if (now_s - self._t_attack_start_s) > self.duration_s:
                if self._attack_active:
                    self._attack_active = False
                    self.get_logger().info("Spoofing attack window ended; releasing HIL_GPS to nominal bridge.")
                self._publish_active(False)
                self._publish_status(False, None, None, None)
                return

        if self._latest_navsat is None or self._latest_odom is None:
            return

        if not self._attack_active:
            self._attack_active = True
            self._compute_spoof_offset(now_s)
            self.get_logger().warn(
                f"GPS SPOOFING ATTACK STARTED! mode={self.mode} rate={self.rate_mps}m/s "
                f"bearing={self.bearing_deg}deg"
            )
        else:
            self._compute_spoof_offset(now_s)

        # Claim HIL_GPS channel so sensor_bridge_node stops sending nominal GPS
        self._publish_active(True)

        # True vehicle state + slight sensor noise + spoofed NED offset
        n_pos = self._rng.normal(0.0, [0.15, 0.15, 0.10])
        n_vel = self._rng.normal(0.0, [0.05, 0.05, 0.05])

        lat_rad = math.radians(self._latest_navsat.latitude)
        dn = self._spoof_pos_ned[0] + n_pos[0]
        de = self._spoof_pos_ned[1] + n_pos[1]
        dd = self._spoof_pos_ned[2] + n_pos[2]

        spoof_lat = self._latest_navsat.latitude + math.degrees(dn / EARTH_RADIUS_M)
        spoof_lon = self._latest_navsat.longitude + math.degrees(de / (EARTH_RADIUS_M * math.cos(lat_rad)))
        spoof_alt = self._latest_navsat.altitude - dd

        gt_vel = self._latest_odom.twist.twist.linear
        spoof_vn = float(gt_vel.x + self._spoof_vel_ned[0] + n_vel[0])
        spoof_ve = float(gt_vel.y + self._spoof_vel_ned[1] + n_vel[1])
        spoof_vd = float(gt_vel.z + self._spoof_vel_ned[2] + n_vel[2])
        speed = math.hypot(spoof_vn, spoof_ve)
        cog_deg = (math.degrees(math.atan2(spoof_ve, spoof_vn)) + 360.0) % 360.0

        usec = (time.monotonic_ns() - self._boot_wall_ns) // 1000
        self.mav.mav.hil_gps_send(
            usec,
            3,                                      # 3D fix (spoofer mimics valid receiver)
            int(round(spoof_lat * 1e7)),
            int(round(spoof_lon * 1e7)),
            int(round(spoof_alt * 1000.0)),
            90,                                     # eph [cm]
            150,                                    # epv [cm]
            int(round(speed * 100.0)),
            int(round(spoof_vn * 100.0)),
            int(round(spoof_ve * 100.0)),
            int(round(spoof_vd * 100.0)),
            int(round(cog_deg * 100.0)),
            12,
        )

        self._publish_status(True, spoof_lat, spoof_lon, (spoof_vn, spoof_ve, spoof_vd))

    def _publish_status(
        self,
        active: bool,
        spoof_lat: Optional[float],
        spoof_lon: Optional[float],
        spoof_vel: Optional[tuple],
    ) -> None:
        payload = {
            "active": active,
            "mode": self.mode if active else "none",
            "t_attack_start_ns": self._t_attack_start_ns,
            "elapsed_s": round(time.monotonic() - self._t_attack_start_s, 3)
            if (active and self._t_attack_start_s is not None)
            else 0.0,
            "rate_mps": self.rate_mps,
            "bearing_deg": self.bearing_deg,
            "offset_ned": [round(float(x), 3) for x in self._spoof_pos_ned],
            "vel_bias_ned": [round(float(x), 3) for x in self._spoof_vel_ned],
            "spoof_lat": spoof_lat,
            "spoof_lon": spoof_lon,
            "spoof_vel_ned": [round(float(v), 3) for v in spoof_vel] if spoof_vel else None,
        }
        msg = String()
        msg.data = json.dumps(payload)
        self.status_pub.publish(msg)

    def shutdown_release(self) -> None:
        if not rclpy.ok():
            return
        try:
            self._publish_active(False)
            self._publish_status(False, None, None, None)
        except Exception:
            pass


def parse_cli_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Adversary GPS Spoofer Node")
    parser.add_argument("--mode", choices=["step", "drift", "takeover"], default="drift")
    parser.add_argument("--rate-mps", type=float, default=2.0, help="Drift/takeover speed [m/s]")
    parser.add_argument("--bearing-deg", type=float, default=0.0, help="Attack vector bearing [deg, 0=N, 90=E]")
    parser.add_argument("--offset-n", type=float, default=15.0, help="Step offset North [m]")
    parser.add_argument("--offset-e", type=float, default=0.0, help="Step offset East [m]")
    parser.add_argument("--offset-d", type=float, default=0.0, help="Step offset Down [m]")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay before attack starts [s]")
    parser.add_argument("--duration", type=float, default=0.0, help="Attack duration [s], 0=infinite")
    parser.add_argument("--ramp-s", type=float, default=2.5, help="Takeover smooth ramp duration [s]")
    parser.add_argument("--mavlink-url", default="udpout:127.0.0.1:13030")
    known, _ = parser.parse_known_args(argv)
    return known


def main(args=None) -> None:
    cli = parse_cli_args(sys.argv[1:])
    rclpy.init(args=args)
    node = AdversarySpooferNode(
        mode=cli.mode,
        rate_mps=cli.rate_mps,
        bearing_deg=cli.bearing_deg,
        offset_n=cli.offset_n,
        offset_e=cli.offset_e,
        offset_d=cli.offset_d,
        delay_s=cli.delay,
        duration_s=cli.duration,
        ramp_s=cli.ramp_s,
        mavlink_url=cli.mavlink_url,
    )
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception:
        if rclpy.ok():
            raise
    finally:
        node.shutdown_release()
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

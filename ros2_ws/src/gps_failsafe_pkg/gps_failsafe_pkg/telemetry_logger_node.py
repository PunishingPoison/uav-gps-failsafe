#!/usr/bin/env python3
"""Synchronized 20 Hz PX4 + Gazebo + Adversary telemetry CSV logger.

Subscribes to all observable PX4 uXRCE-DDS topics with PX4 BEST_EFFORT QoS,
plus /uav/optical_flow, /uav/ground_truth_odom, /mission/status, /adversary/attack_status,
and /guardian/failover_active, exporting self-contained CSV logs for training and evaluation.
"""

import argparse
import csv
import json
import math
from pathlib import Path
import sys
import time
from typing import Any, Dict, Optional

from nav_msgs.msg import Odometry
from px4_msgs.msg import (
    EstimatorStatusFlags,
    SensorCombined,
    SensorGps,
    VehicleAttitude,
    VehicleLocalPosition,
    VehicleStatus,
)
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Bool, String

from gps_failsafe_pkg.qos_profiles import px4_sub_qos


CSV_COLUMNS = [
    "timestamp_s",
    "wall_time_ns",
    "episode_id",
    "mission_pattern",
    "mission_phase",
    "target_n",
    "target_e",
    "target_d",
    "spoof_active",
    "attack_mode",
    "attack_elapsed_s",
    "spoof_off_n",
    "spoof_off_e",
    "guardian_active",
    "gt_x",
    "gt_y",
    "gt_z",
    "gt_vx",
    "gt_vy",
    "gt_vz",
    "gps_lat",
    "gps_lon",
    "gps_alt",
    "gps_vn",
    "gps_ve",
    "gps_vd",
    "gps_speed",
    "gps_eph",
    "gps_epv",
    "gps_sacc",
    "gps_fix",
    "gps_sats",
    "est_x",
    "est_y",
    "est_z",
    "est_vx",
    "est_vy",
    "est_vz",
    "est_ax",
    "est_ay",
    "est_az",
    "est_ref_lat",
    "est_ref_lon",
    "est_ref_alt",
    "est_eph",
    "est_epv",
    "est_evh",
    "est_dist_bottom",
    "est_dist_valid",
    "est_xy_valid",
    "est_z_valid",
    "est_xy_global",
    "est_dead_reckoning",
    "est_heading",
    "att_qw",
    "att_qx",
    "att_qy",
    "att_qz",
    "imu_gx",
    "imu_gy",
    "imu_gz",
    "imu_ax",
    "imu_ay",
    "imu_az",
    "of_flow_x",
    "of_flow_y",
    "of_dt_s",
    "of_range_m",
    "of_quality",
    "cs_gps",
    "cs_opt_flow",
    "cs_rng_hgt",
    "reject_hor_pos",
    "reject_hor_vel",
    "arming_state",
    "nav_state",
]


class TelemetryLoggerNode(Node):
    """Samples synchronized multi-topic drone telemetry to a labeled CSV file."""

    def __init__(
        self,
        output_path: str,
        episode_id: str = "ep_001",
        rate_hz: float = 20.0,
    ) -> None:
        super().__init__("telemetry_logger_node")
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.episode_id = episode_id
        self.rate_hz = max(1.0, float(rate_hz))

        self._start_s = time.monotonic()
        self._row_count = 0

        self._gps: Optional[SensorGps] = None
        self._lpos: Optional[VehicleLocalPosition] = None
        self._att: Optional[VehicleAttitude] = None
        self._imu: Optional[SensorCombined] = None
        self._flags: Optional[EstimatorStatusFlags] = None
        self._vstatus: Optional[VehicleStatus] = None
        self._gt: Optional[Odometry] = None
        self._flow: Optional[Dict[str, Any]] = None
        self._mission: Optional[Dict[str, Any]] = None
        self._adversary: Optional[Dict[str, Any]] = None
        self._adv_last_rx_s = 0.0
        self._guardian_active = False

        sub_q = px4_sub_qos()
        self.create_subscription(SensorGps, "/fmu/out/vehicle_gps_position", self._on_gps, sub_q)
        self.create_subscription(VehicleLocalPosition, "/fmu/out/vehicle_local_position", self._on_lpos, sub_q)
        self.create_subscription(VehicleAttitude, "/fmu/out/vehicle_attitude", self._on_att, sub_q)
        self.create_subscription(SensorCombined, "/fmu/out/sensor_combined", self._on_imu, sub_q)
        self.create_subscription(EstimatorStatusFlags, "/fmu/out/estimator_status_flags", self._on_flags, sub_q)
        self.create_subscription(VehicleStatus, "/fmu/out/vehicle_status", self._on_vstatus, sub_q)

        self.create_subscription(Odometry, "/uav/ground_truth_odom", self._on_gt, 10)
        self.create_subscription(String, "/uav/optical_flow", self._on_flow, 10)
        self.create_subscription(String, "/mission/status", self._on_mission, 10)
        self.create_subscription(String, "/adversary/attack_status", self._on_adversary, 10)
        self.create_subscription(Bool, "/guardian/failover_active", self._on_guardian, 10)

        self._csv_file = open(self.output_path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._csv_file, fieldnames=CSV_COLUMNS)
        self._writer.writeheader()
        self._csv_file.flush()

        self.create_timer(1.0 / self.rate_hz, self._sample)
        self.get_logger().info(
            f"Telemetry logger active -> {self.output_path} (episode={self.episode_id}, {self.rate_hz:.1f} Hz)"
        )

    def _on_gps(self, msg: SensorGps) -> None:
        self._gps = msg

    def _on_lpos(self, msg: VehicleLocalPosition) -> None:
        self._lpos = msg

    def _on_att(self, msg: VehicleAttitude) -> None:
        self._att = msg

    def _on_imu(self, msg: SensorCombined) -> None:
        self._imu = msg

    def _on_flags(self, msg: EstimatorStatusFlags) -> None:
        self._flags = msg

    def _on_vstatus(self, msg: VehicleStatus) -> None:
        self._vstatus = msg

    def _on_gt(self, msg: Odometry) -> None:
        self._gt = msg

    def _on_flow(self, msg: String) -> None:
        try:
            self._flow = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def _on_mission(self, msg: String) -> None:
        try:
            self._mission = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def _on_adversary(self, msg: String) -> None:
        try:
            self._adversary = json.loads(msg.data)
            self._adv_last_rx_s = time.monotonic()
        except json.JSONDecodeError:
            pass

    def _on_guardian(self, msg: Bool) -> None:
        self._guardian_active = bool(msg.data)

    def _sample(self) -> None:
        if self._gps is None or self._lpos is None or self._att is None or self._imu is None:
            return

        now_s = time.monotonic()
        wall_ns = self.get_clock().now().nanoseconds

        # Adversary active flag times out cleanly if spoofer exits
        adv = self._adversary if (self._adversary and (now_s - self._adv_last_rx_s) < 1.0) else None
        spoof_active = 1 if (adv and adv.get("active")) else 0
        attack_mode = str(adv.get("mode", "none")) if spoof_active else "none"
        attack_elapsed_s = float(adv.get("elapsed_s", 0.0)) if spoof_active else 0.0
        off_ned = adv.get("offset_ned", [0.0, 0.0, 0.0]) if spoof_active else [0.0, 0.0, 0.0]

        mis = self._mission or {}
        tgt = mis.get("target_ned", [math.nan, math.nan, math.nan])

        gt_p = self._gt.pose.pose.position if self._gt else None
        gt_v = self._gt.twist.twist.linear if self._gt else None
        flow = self._flow or {}
        fl = self._flags
        vs = self._vstatus

        row = {
            "timestamp_s": round(now_s - self._start_s, 4),
            "wall_time_ns": int(wall_ns),
            "episode_id": self.episode_id,
            "mission_pattern": mis.get("pattern", "unknown"),
            "mission_phase": mis.get("phase", "UNKNOWN"),
            "target_n": float(tgt[0]),
            "target_e": float(tgt[1]),
            "target_d": float(tgt[2]),
            "spoof_active": spoof_active,
            "attack_mode": attack_mode,
            "attack_elapsed_s": round(attack_elapsed_s, 4),
            "spoof_off_n": float(off_ned[0]),
            "spoof_off_e": float(off_ned[1]),
            "guardian_active": 1 if self._guardian_active else 0,
            "gt_x": float(gt_p.x) if gt_p else math.nan,
            "gt_y": float(gt_p.y) if gt_p else math.nan,
            "gt_z": float(gt_p.z) if gt_p else math.nan,
            "gt_vx": float(gt_v.x) if gt_v else math.nan,
            "gt_vy": float(gt_v.y) if gt_v else math.nan,
            "gt_vz": float(gt_v.z) if gt_v else math.nan,
            "gps_lat": float(self._gps.latitude_deg),
            "gps_lon": float(self._gps.longitude_deg),
            "gps_alt": float(self._gps.altitude_msl_m),
            "gps_vn": float(self._gps.vel_n_m_s),
            "gps_ve": float(self._gps.vel_e_m_s),
            "gps_vd": float(self._gps.vel_d_m_s),
            "gps_speed": float(self._gps.vel_m_s),
            "gps_eph": float(self._gps.eph),
            "gps_epv": float(self._gps.epv),
            "gps_sacc": float(self._gps.s_variance_m_s),
            "gps_fix": int(self._gps.fix_type),
            "gps_sats": int(self._gps.satellites_used),
            "est_x": float(self._lpos.x),
            "est_y": float(self._lpos.y),
            "est_z": float(self._lpos.z),
            "est_vx": float(self._lpos.vx),
            "est_vy": float(self._lpos.vy),
            "est_vz": float(self._lpos.vz),
            "est_ax": float(self._lpos.ax),
            "est_ay": float(self._lpos.ay),
            "est_az": float(self._lpos.az),
            "est_ref_lat": float(self._lpos.ref_lat),
            "est_ref_lon": float(self._lpos.ref_lon),
            "est_ref_alt": float(self._lpos.ref_alt),
            "est_eph": float(self._lpos.eph),
            "est_epv": float(self._lpos.epv),
            "est_evh": float(self._lpos.evh),
            "est_dist_bottom": float(self._lpos.dist_bottom),
            "est_dist_valid": 1 if self._lpos.dist_bottom_valid else 0,
            "est_xy_valid": 1 if self._lpos.xy_valid else 0,
            "est_z_valid": 1 if self._lpos.z_valid else 0,
            "est_xy_global": 1 if self._lpos.xy_global else 0,
            "est_dead_reckoning": 1 if self._lpos.dead_reckoning else 0,
            "est_heading": float(self._lpos.heading),
            "att_qw": float(self._att.q[0]),
            "att_qx": float(self._att.q[1]),
            "att_qy": float(self._att.q[2]),
            "att_qz": float(self._att.q[3]),
            "imu_gx": float(self._imu.gyro_rad[0]),
            "imu_gy": float(self._imu.gyro_rad[1]),
            "imu_gz": float(self._imu.gyro_rad[2]),
            "imu_ax": float(self._imu.accelerometer_m_s2[0]),
            "imu_ay": float(self._imu.accelerometer_m_s2[1]),
            "imu_az": float(self._imu.accelerometer_m_s2[2]),
            "of_flow_x": float(flow.get("pixel_flow_x", 0.0)),
            "of_flow_y": float(flow.get("pixel_flow_y", 0.0)),
            "of_dt_s": float(flow.get("dt_s", 0.0)),
            "of_range_m": float(flow.get("range_m", -1.0)),
            "of_quality": int(flow.get("quality", 0)),
            "cs_gps": 1 if (fl and fl.cs_gps) else 0,
            "cs_opt_flow": 1 if (fl and fl.cs_opt_flow) else 0,
            "cs_rng_hgt": 1 if (fl and fl.cs_rng_hgt) else 0,
            "reject_hor_pos": 1 if (fl and fl.reject_hor_pos) else 0,
            "reject_hor_vel": 1 if (fl and fl.reject_hor_vel) else 0,
            "arming_state": int(vs.arming_state) if vs else 0,
            "nav_state": int(vs.nav_state) if vs else 0,
        }
        self._writer.writerow(row)
        self._row_count += 1
        if self._row_count % 20 == 0:
            self._csv_file.flush()

    def close(self) -> None:
        if self._csv_file and not self._csv_file.closed:
            self._csv_file.flush()
            self._csv_file.close()


def parse_cli_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synchronized PX4 + Gazebo telemetry CSV logger")
    parser.add_argument(
        "--output",
        default="/uav_ws/data/raw/flight_log.csv",
        help="Output CSV path",
    )
    parser.add_argument("--episode-id", default="ep_001", help="Episode identifier string")
    parser.add_argument("--rate-hz", type=float, default=20.0, help="Logging rate [Hz]")
    known, _ = parser.parse_known_args(argv)
    return known


def main(args=None) -> None:
    cli = parse_cli_args(sys.argv[1:])
    rclpy.init(args=args)
    node = TelemetryLoggerNode(
        output_path=cli.output,
        episode_id=cli.episode_id,
        rate_hz=cli.rate_hz,
    )
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception:
        if rclpy.ok():
            raise
    finally:
        node.close()
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Real-time AI Guardian node for GPS spoofing detection and automated PX4 failsafe.

Continuously monitors onboard telemetry at 20 Hz using FeatureWindowExtractor,
runs ML inference (Random Forest or XGBoost), and upon sustained positive detection:
  1. Publishes /guardian/failover_active = True to preempt Offboard mission waypoints.
  2. Commands PX4 to Hold (AUTO.LOITER) immediately.
  3. Sets EKF2_GPS_CTRL=0, EKF2_HGT_REF=2, EKF2_OF_CTRL=1, EKF2_RNG_CTRL=2 via MAVLink.
"""

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, Optional

import joblib
import numpy as np
from px4_msgs.msg import (
    EstimatorStatusFlags,
    SensorCombined,
    SensorGps,
    VehicleAttitude,
    VehicleCommand,
    VehicleLocalPosition,
    VehicleStatus,
)
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Bool, String

from gps_failsafe_pkg.ekf2_param_client import (
    apply_ekf2_mode,
    connect_px4,
    drain_mavlink_rx,
)
from gps_failsafe_pkg.feature_extractor import FEATURE_NAMES, FeatureWindowExtractor
from gps_failsafe_pkg.qos_profiles import px4_pub_qos, px4_sub_qos


DEFAULT_MODELS_DIR = Path("/uav_ws/ml/models")
if not DEFAULT_MODELS_DIR.exists():
    DEFAULT_MODELS_DIR = Path(__file__).resolve().parents[4] / "ml" / "models"


class GuardianAINode(Node):
    """Real-time ML spoofing detector that triggers GPS-denied Optical Flow + LiDAR hover."""

    def __init__(
        self,
        model_choice: str = "rf",
        models_dir: str = str(DEFAULT_MODELS_DIR),
        threshold: float = -1.0,
        consecutive: int = 5,
        settle_s: float = 2.5,
        rate_hz: float = 20.0,
        mavlink_url: str = "udpin:0.0.0.0:14540",
        dry_run: bool = False,
    ) -> None:
        super().__init__("guardian_ai_node")

        mdir = Path(models_dir)
        meta_path = mdir / "model_metadata.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Missing model metadata: {meta_path}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

        model_file = mdir / ("rf_detector.joblib" if model_choice == "rf" else "xgb_detector.joblib")
        if not model_file.exists():
            raise FileNotFoundError(f"Missing trained model: {model_file}")

        expected_features = list(meta["feature_names"])
        if expected_features != list(FEATURE_NAMES):
            raise RuntimeError("Feature schema mismatch between model_metadata.json and feature_extractor.py")

        self.model = joblib.load(model_file)
        self.model_choice = model_choice
        # Conservative threshold calibrated for zero false alarms under fast maneuvers
        default_th = 0.80 if model_choice == "rf" else float(meta["recommended_thresholds"].get("xgboost", 0.82))
        self.threshold = default_th if threshold < 0.0 else float(threshold)
        self.consecutive = max(1, int(consecutive))
        self.settle_s = max(0.0, float(settle_s))
        self.rate_hz = max(1.0, float(rate_hz))
        self.dry_run = bool(dry_run)

        window_size = int(meta.get("window_size", 20))
        min_samples = int(meta.get("min_samples", 10))
        self.extractor = FeatureWindowExtractor(window_size=window_size, min_samples=min_samples)

        self.mav = None
        if not self.dry_run:
            self.get_logger().info(f"Pre-connecting MAVLink control channel on {mavlink_url}...")
            self.mav = connect_px4(mavlink_url, timeout=25.0)
            self.get_logger().info(
                f"MAVLink linked (sys={self.mav.target_system}, comp={self.mav.target_component})"
            )

        self._gps: Optional[SensorGps] = None
        self._lpos: Optional[VehicleLocalPosition] = None
        self._att: Optional[VehicleAttitude] = None
        self._imu: Optional[SensorCombined] = None
        self._flags: Optional[EstimatorStatusFlags] = None
        self._vstatus: Optional[VehicleStatus] = None
        self._flow: Optional[Dict[str, Any]] = None

        self._t0_s = time.monotonic()
        self._airborne_since_s: Optional[float] = None
        self._consec_hits = 0
        self._failover_active = False
        self._t_failover_s: Optional[float] = None
        self._failover_latency_ms: Optional[float] = None
        self._last_prob = 0.0

        sub_q = px4_sub_qos()
        pub_q = px4_pub_qos()
        self.create_subscription(SensorGps, "/fmu/out/vehicle_gps_position", lambda m: setattr(self, "_gps", m), sub_q)
        self.create_subscription(VehicleLocalPosition, "/fmu/out/vehicle_local_position", lambda m: setattr(self, "_lpos", m), sub_q)
        self.create_subscription(VehicleAttitude, "/fmu/out/vehicle_attitude", lambda m: setattr(self, "_att", m), sub_q)
        self.create_subscription(SensorCombined, "/fmu/out/sensor_combined", lambda m: setattr(self, "_imu", m), sub_q)
        self.create_subscription(EstimatorStatusFlags, "/fmu/out/estimator_status_flags", lambda m: setattr(self, "_flags", m), sub_q)
        self.create_subscription(VehicleStatus, "/fmu/out/vehicle_status", lambda m: setattr(self, "_vstatus", m), sub_q)
        self.create_subscription(String, "/uav/optical_flow", self._on_flow, 10)

        self.pub_cmd = self.create_publisher(VehicleCommand, "/fmu/in/vehicle_command", pub_q)
        self.pub_failover = self.create_publisher(Bool, "/guardian/failover_active", 10)
        self.pub_status = self.create_publisher(String, "/guardian/status", 10)

        self.create_timer(1.0 / self.rate_hz, self._tick)
        self.create_timer(0.2, self._maintain_failover)

        self.get_logger().info(
            f"Guardian AI ready: model={model_choice} ({model_file.name}), "
            f"threshold={self.threshold:.2f}, consecutive={self.consecutive}, settle={self.settle_s:.1f}s"
        )

    def _on_flow(self, msg: String) -> None:
        try:
            self._flow = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def _send_hold_mode(self) -> None:
        """Command PX4 AUTO.LOITER (Hold mode: custom main=4, sub=3) over uXRCE-DDS."""
        msg = VehicleCommand()
        msg.timestamp = int(self.get_clock().now().nanoseconds // 1000)
        msg.command = VehicleCommand.VEHICLE_CMD_DO_SET_MODE
        msg.param1 = 1.0  # MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
        msg.param2 = 4.0  # PX4_CUSTOM_MAIN_MODE_AUTO
        msg.param3 = 3.0  # PX4_CUSTOM_SUB_MODE_AUTO_LOITER
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self.pub_cmd.publish(msg)

    def _maintain_failover(self) -> None:
        """Drain MAVLink RX before failover and hold AUTO.LOITER after failover triggers."""
        if self.mav is not None and not self._failover_active:
            drain_mavlink_rx(self.mav, max_msgs=64)

        b = Bool()
        b.data = self._failover_active
        self.pub_failover.publish(b)

        if self._failover_active and not self.dry_run:
            if self._vstatus is None or self._vstatus.nav_state != VehicleStatus.NAVIGATION_STATE_AUTO_LOITER:
                self._send_hold_mode()

    def _trigger_failover(self) -> None:
        t_start = time.monotonic()
        self._failover_active = True
        self._t_failover_s = t_start

        b = Bool()
        b.data = True
        self.pub_failover.publish(b)

        if not self.dry_run:
            self._send_hold_mode()
            if self.mav is not None:
                applied = apply_ekf2_mode(self.mav, "gps-denied", force=True, fast_cutover=True)
                self._send_hold_mode()
                self._failover_latency_ms = round((time.monotonic() - t_start) * 1000.0, 2)
                self.get_logger().error(
                    f"GPS SPOOFING DETECTED (p={self._last_prob:.3f})! "
                    f"Failover executed in {self._failover_latency_ms:.1f} ms -> {applied} & AUTO.LOITER commanded."
                )
        else:
            self._failover_latency_ms = 0.0
            self.get_logger().warn(f"[DRY-RUN] GPS SPOOFING DETECTED (p={self._last_prob:.3f})")

    def _build_sample_dict(self, now_s: float) -> Optional[Dict[str, float]]:
        if self._gps is None or self._lpos is None or self._att is None or self._imu is None:
            return None
        flow = self._flow or {}
        return {
            "timestamp_s": now_s - self._t0_s,
            "gps_lat": float(self._gps.latitude_deg),
            "gps_lon": float(self._gps.longitude_deg),
            "gps_alt": float(self._gps.altitude_msl_m),
            "gps_vn": float(self._gps.vel_n_m_s),
            "gps_ve": float(self._gps.vel_e_m_s),
            "est_x": float(self._lpos.x),
            "est_y": float(self._lpos.y),
            "est_z": float(self._lpos.z),
            "est_vx": float(self._lpos.vx),
            "est_vy": float(self._lpos.vy),
            "est_ref_lat": float(self._lpos.ref_lat),
            "est_ref_lon": float(self._lpos.ref_lon),
            "est_ref_alt": float(self._lpos.ref_alt),
            "att_qw": float(self._att.q[0]),
            "att_qx": float(self._att.q[1]),
            "att_qy": float(self._att.q[2]),
            "att_qz": float(self._att.q[3]),
            "imu_gx": float(self._imu.gyro_rad[0]),
            "imu_gy": float(self._imu.gyro_rad[1]),
            "imu_ax": float(self._imu.accelerometer_m_s2[0]),
            "imu_ay": float(self._imu.accelerometer_m_s2[1]),
            "imu_az": float(self._imu.accelerometer_m_s2[2]),
            "of_flow_x": float(flow.get("pixel_flow_x", 0.0)),
            "of_flow_y": float(flow.get("pixel_flow_y", 0.0)),
            "of_dt_s": float(flow.get("dt_s", 0.0)),
            "of_range_m": float(flow.get("range_m", -1.0)),
            "of_quality": float(flow.get("quality", 0.0)),
        }

    def _tick(self) -> None:
        now_s = time.monotonic()
        sample = self._build_sample_dict(now_s)
        if sample is None or self._vstatus is None:
            return

        airborne = (
            self._vstatus.arming_state == VehicleStatus.ARMING_STATE_ARMED
            and bool(self._lpos.xy_valid)
            and bool(self._lpos.xy_global)
            and float(self._lpos.z) < -1.5
        )
        if not airborne:
            self._airborne_since_s = None
            self._consec_hits = 0
            self.extractor.reset()
            self._publish_status(armed_guardian=False)
            return

        if self._airborne_since_s is None:
            self._airborne_since_s = now_s
            self.get_logger().info(f"Airborne climb complete; Guardian warming up ({self.settle_s:.1f}s)...")

        feats = self.extractor.push_and_extract(sample)
        if feats is None or (now_s - self._airborne_since_s) < self.settle_s:
            self._publish_status(armed_guardian=False)
            return

        if not self._failover_active:
            prob = float(self.model.predict_proba(feats.reshape(1, -1))[0, 1])
            self._last_prob = prob
            if prob >= self.threshold:
                self._consec_hits += 1
            else:
                self._consec_hits = 0

            if self._consec_hits >= self.consecutive:
                self._trigger_failover()

        self._publish_status(armed_guardian=True)

    def _publish_status(self, armed_guardian: bool) -> None:
        fl = self._flags
        vs = self._vstatus
        payload = {
            "model": self.model_choice,
            "threshold": self.threshold,
            "guardian_monitoring": armed_guardian and not self._failover_active,
            "failover_active": self._failover_active,
            "spoof_prob": round(self._last_prob, 4),
            "consec_hits": int(self._consec_hits),
            "failover_exec_ms": self._failover_latency_ms,
            "cs_gps": bool(fl.cs_gps) if fl else None,
            "cs_opt_flow": bool(fl.cs_opt_flow) if fl else None,
            "cs_rng_hgt": bool(fl.cs_rng_hgt) if fl else None,
            "nav_state": int(vs.nav_state) if vs else None,
        }
        msg = String()
        msg.data = json.dumps(payload)
        self.pub_status.publish(msg)


def parse_cli_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Real-time AI Guardian GPS Spoofing Failsafe Node")
    parser.add_argument("--model", choices=["rf", "xgb"], default="rf", help="Trained classifier to deploy")
    parser.add_argument("--models-dir", default=str(DEFAULT_MODELS_DIR))
    parser.add_argument("--threshold", type=float, default=-1.0, help="Override probability threshold (<0 uses calibrated default)")
    parser.add_argument("--consecutive", type=int, default=5, help="Consecutive positive ticks before triggering failover")
    parser.add_argument("--settle-s", type=float, default=2.5, help="Post-takeoff warmup settle before enabling detection [s]")
    parser.add_argument("--rate-hz", type=float, default=20.0, help="Inference rate [Hz]")
    parser.add_argument("--mavlink-url", default="udpin:0.0.0.0:14540")
    parser.add_argument("--dry-run", action="store_true", help="Detect and log without changing PX4 parameters")
    known, _ = parser.parse_known_args(argv)
    return known


def main(args=None) -> None:
    cli = parse_cli_args(sys.argv[1:])
    rclpy.init(args=args)
    node = GuardianAINode(
        model_choice=cli.model,
        models_dir=cli.models_dir,
        threshold=cli.threshold,
        consecutive=cli.consecutive,
        settle_s=cli.settle_s,
        rate_hz=cli.rate_hz,
        mavlink_url=cli.mavlink_url,
        dry_run=cli.dry_run,
    )
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception:
        if rclpy.ok():
            raise
    finally:
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Bridges Gazebo downward camera, 1D LiDAR, and nominal GNSS into PX4.

- Downward 1D LiDAR (/gz/downward_lidar/scan) -> MAVLink DISTANCE_SENSOR (30 Hz)
- Downward camera (/gz/downward_camera/image) -> MAVLink OPTICAL_FLOW_RAD (30 Hz)
- Gazebo NavSat (/gz/navsat) + Pose (/gz/pose/info) ->
    * /uav/ground_truth_odom (nav_msgs/Odometry in NED frame)
    * /uav/ground_truth_navsat (sensor_msgs/NavSatFix)
    * Nominal MAVLink HIL_GPS (10 Hz) whenever /adversary/active is False/absent
"""

import json
import math
import time
from typing import Optional

import cv2
import numpy as np
from pymavlink import mavutil
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image, LaserScan, NavSatFix
from std_msgs.msg import Bool, String


class SensorBridgeNode(Node):
    """Bridges Gazebo Harmonic sensors and ground-truth state to PX4 & ROS 2."""

    def __init__(self) -> None:
        super().__init__("sensor_bridge_node")

        self.declare_parameter("mavlink_url", "udpin:0.0.0.0:14030")
        self.declare_parameter("model_name", "x500_flow_lidar_0")
        self.declare_parameter("camera_hfov_rad", 0.80)
        self.declare_parameter("lidar_min_m", 0.08)
        self.declare_parameter("lidar_max_m", 60.0)
        self.declare_parameter("gps_rate_hz", 10.0)

        mav_url = self.get_parameter("mavlink_url").get_parameter_value().string_value
        self.model_name = self.get_parameter("model_name").get_parameter_value().string_value
        self.hfov_rad = self.get_parameter("camera_hfov_rad").get_parameter_value().double_value
        self.lidar_min_m = self.get_parameter("lidar_min_m").get_parameter_value().double_value
        self.lidar_max_m = self.get_parameter("lidar_max_m").get_parameter_value().double_value
        gps_rate_hz = self.get_parameter("gps_rate_hz").get_parameter_value().double_value

        self.get_logger().info(f"Connecting MAVLink sensor link on {mav_url}...")
        self.mav = mavutil.mavlink_connection(mav_url, source_system=1, source_component=190)
        hb = self.mav.wait_heartbeat(timeout=30.0)
        if hb is None:
            raise RuntimeError(f"Timed out waiting for PX4 heartbeat on {mav_url}")
        self.get_logger().info(
            f"PX4 heartbeat received (sys={self.mav.target_system}, comp={self.mav.target_component})"
        )

        self._rng = np.random.default_rng(12345)
        self._boot_wall_ns = time.monotonic_ns()

        # Sensor states
        self._latest_range_m: Optional[float] = None
        self._prev_gray: Optional[np.ndarray] = None
        self._prev_cam_time_ns: Optional[int] = None
        self._focal_px: Optional[float] = None
        self._lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 15, 0.03),
        )

        # Ground-truth state (NED)
        self._gt_pos_ned = np.zeros(3, dtype=np.float64)
        self._gt_vel_ned = np.zeros(3, dtype=np.float64)
        self._gt_quat_frd_ned = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)  # w, x, y, z
        self._prev_gt_pos_ned: Optional[np.ndarray] = None
        self._prev_gt_time_s: Optional[float] = None
        self._has_pose = False

        self._latest_navsat: Optional[NavSatFix] = None

        # Adversary preemption tracking
        self._adversary_active = False
        self._last_adversary_msg_s = 0.0

        # Stats
        self._cnt_lidar = 0
        self._cnt_flow = 0
        self._cnt_gps = 0
        self._last_flow_quality = 0

        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
        )

        self.create_subscription(LaserScan, "/gz/downward_lidar/scan", self._on_lidar, sensor_qos)
        self.create_subscription(Image, "/gz/downward_camera/image", self._on_camera, sensor_qos)
        self.create_subscription(NavSatFix, "/gz/navsat", self._on_navsat, sensor_qos)
        self.create_subscription(Odometry, "/gz/ground_truth/odom", self._on_gz_odom, sensor_qos)
        self.create_subscription(Bool, "/adversary/active", self._on_adversary_active, 10)

        self.gt_odom_pub = self.create_publisher(Odometry, "/uav/ground_truth_odom", 10)
        self.gt_navsat_pub = self.create_publisher(NavSatFix, "/uav/ground_truth_navsat", 10)
        self.status_pub = self.create_publisher(String, "/uav/sensor_bridge_status", 10)

        self.create_timer(1.0 / gps_rate_hz, self._send_nominal_gps)
        self.create_timer(1.0, self._publish_status)

    def _usec_now(self) -> int:
        return (time.monotonic_ns() - self._boot_wall_ns) // 1000

    def _on_adversary_active(self, msg: Bool) -> None:
        self._adversary_active = bool(msg.data)
        if self._adversary_active:
            self._last_adversary_msg_s = time.monotonic()

    def _on_lidar(self, msg: LaserScan) -> None:
        if not msg.ranges:
            return
        r = float(msg.ranges[len(msg.ranges) // 2])
        if not math.isfinite(r):
            r = self.lidar_max_m
        r = max(self.lidar_min_m, min(self.lidar_max_m, r))
        self._latest_range_m = r

        self.mav.mav.distance_sensor_send(
            int((self._usec_now() // 1000) & 0xFFFFFFFF),  # time_boot_ms
            int(round(self.lidar_min_m * 100.0)),           # min_distance [cm]
            int(round(self.lidar_max_m * 100.0)),           # max_distance [cm]
            int(round(r * 100.0)),                          # current_distance [cm]
            mavutil.mavlink.MAV_DISTANCE_SENSOR_LASER,      # type
            0,                                              # id
            mavutil.mavlink.MAV_SENSOR_ROTATION_PITCH_270,  # orientation = downward (25)
            1,                                              # covariance [cm^2]
            0.01,                                           # horizontal_fov
            0.01,                                           # vertical_fov
            [1.0, 0.0, 0.0, 0.0],                           # quaternion
            100,                                            # signal_quality (1..100)
        )
        self._cnt_lidar += 1

    def _on_camera(self, msg: Image) -> None:
        channels = max(1, len(msg.data) // max(1, msg.height * msg.width))
        frame = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, channels))
        if channels == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        elif channels == 4:
            gray = cv2.cvtColor(frame, cv2.COLOR_RGBA2GRAY)
        else:
            gray = frame[:, :, 0]

        if self._focal_px is None:
            self._focal_px = (msg.width / 2.0) / math.tan(self.hfov_rad / 2.0)

        now_ns = (
            msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
            if msg.header.stamp.sec > 0
            else time.monotonic_ns()
        )

        if self._prev_gray is None or self._prev_cam_time_ns is None:
            self._prev_gray = gray
            self._prev_cam_time_ns = now_ns
            return

        dt_us = max(1000, (now_ns - self._prev_cam_time_ns) // 1000)
        if dt_us > 500_000:
            self._prev_gray = gray
            self._prev_cam_time_ns = now_ns
            return

        p0 = cv2.goodFeaturesToTrack(
            self._prev_gray, maxCorners=60, qualityLevel=0.05, minDistance=8, blockSize=7
        )
        du, dv, quality = 0.0, 0.0, 0
        if p0 is not None and len(p0) >= 6:
            p1, st, _ = cv2.calcOpticalFlowPyrLK(self._prev_gray, gray, p0, None, **self._lk_params)
            if p1 is not None and st is not None:
                good_mask = st.flatten() == 1
                if int(np.sum(good_mask)) >= 5:
                    disp = p1[good_mask].reshape(-1, 2) - p0[good_mask].reshape(-1, 2)
                    du = float(np.median(disp[:, 0]))
                    dv = float(np.median(disp[:, 1]))
                    inliers = np.linalg.norm(disp - np.array([du, dv]), axis=1) < 2.5
                    ratio = float(np.mean(inliers))
                    quality = int(np.clip(round(255.0 * ratio), 40, 255))

        self._prev_gray = gray
        self._prev_cam_time_ns = now_ns
        self._last_flow_quality = quality

        # Image displacement -> PX4 sensor pixel_flow [rad] (see EKF2::UpdateFlowSample)
        px_flow_x = float(du / self._focal_px)
        px_flow_y = float(dv / self._focal_px)
        dist = float(self._latest_range_m) if self._latest_range_m is not None else -1.0

        # Send NaN for integrated gyro so PX4 EKF2 uses its own high-rate IMU gyro
        nan = float("nan")
        self.mav.mav.optical_flow_rad_send(
            self._usec_now(),
            0,          # sensor_id
            int(dt_us), # integration_time_us
            px_flow_x,  # integrated_x [rad]
            px_flow_y,  # integrated_y [rad]
            nan,        # integrated_xgyro
            nan,        # integrated_ygyro
            nan,        # integrated_zgyro
            0,          # temperature
            quality,    # quality (0..255)
            0,          # time_delta_distance_us
            dist,       # distance [m]
        )
        self._cnt_flow += 1

    def _on_navsat(self, msg: NavSatFix) -> None:
        self._latest_navsat = msg
        self.gt_navsat_pub.publish(msg)

    def _on_gz_odom(self, msg: Odometry) -> None:
        # Gazebo OdometryPublisher world frame is ENU (x=East, y=North, z=Up) -> NED
        p = msg.pose.pose.position
        pos_ned = np.array([p.y, p.x, -p.z], dtype=np.float64)

        stamp_s = (
            msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            if msg.header.stamp.sec > 0
            else time.monotonic()
        )
        if self._prev_gt_pos_ned is not None and self._prev_gt_time_s is not None:
            dt = stamp_s - self._prev_gt_time_s
            if 1e-4 < dt < 0.5:
                inst_vel = (pos_ned - self._prev_gt_pos_ned) / dt
                self._gt_vel_ned = 0.5 * self._gt_vel_ned + 0.5 * inst_vel
        self._prev_gt_pos_ned = pos_ned.copy()
        self._prev_gt_time_s = stamp_s
        self._gt_pos_ned = pos_ned
        self._has_pose = True

        # Publish clean NED ground-truth odometry
        odom = Odometry()
        odom.header.stamp = self.get_clock().now().to_msg()
        odom.header.frame_id = "ned"
        odom.child_frame_id = "base_link_frd"
        odom.pose.pose.position.x = float(pos_ned[0])
        odom.pose.pose.position.y = float(pos_ned[1])
        odom.pose.pose.position.z = float(pos_ned[2])
        odom.pose.pose.orientation = msg.pose.pose.orientation
        odom.twist.twist.linear.x = float(self._gt_vel_ned[0])
        odom.twist.twist.linear.y = float(self._gt_vel_ned[1])
        odom.twist.twist.linear.z = float(self._gt_vel_ned[2])
        self.gt_odom_pub.publish(odom)

    def _send_nominal_gps(self) -> None:
        if self._latest_navsat is None or not self._has_pose:
            return

        # Yield cleanly when adversary node is actively streaming spoofed HIL_GPS
        if self._adversary_active and (time.monotonic() - self._last_adversary_msg_s) < 1.5:
            return
        self._adversary_active = False

        # Realistic slight GPS Gaussian noise (matches PX4 SensorGpsSim)
        earth_r = 6371000.0
        n_pos = self._rng.normal(0.0, [0.15, 0.15, 0.10])
        n_vel = self._rng.normal(0.0, [0.05, 0.05, 0.05])

        lat_deg = self._latest_navsat.latitude + math.degrees(n_pos[0] / earth_r)
        lon_deg = self._latest_navsat.longitude + math.degrees(
            n_pos[1] / (earth_r * math.cos(math.radians(self._latest_navsat.latitude)))
        )
        alt_m = self._latest_navsat.altitude + float(n_pos[2])

        vn = float(self._gt_vel_ned[0] + n_vel[0])
        ve = float(self._gt_vel_ned[1] + n_vel[1])
        vd = float(self._gt_vel_ned[2] + n_vel[2])
        speed = math.hypot(vn, ve)
        cog_deg = (math.degrees(math.atan2(ve, vn)) + 360.0) % 360.0

        self.mav.mav.hil_gps_send(
            self._usec_now(),
            3,                                      # fix_type = 3D
            int(round(lat_deg * 1e7)),
            int(round(lon_deg * 1e7)),
            int(round(alt_m * 1000.0)),             # mm
            90,                                     # eph [cm]
            150,                                    # epv [cm]
            int(round(speed * 100.0)),              # vel [cm/s]
            int(round(vn * 100.0)),                 # vn [cm/s]
            int(round(ve * 100.0)),                 # ve [cm/s]
            int(round(vd * 100.0)),                 # vd [cm/s]
            int(round(cog_deg * 100.0)),            # cog [cdeg]
            12,                                     # satellites_visible
        )
        self._cnt_gps += 1

    def _publish_status(self) -> None:
        payload = {
            "lidar_hz_total": self._cnt_lidar,
            "flow_hz_total": self._cnt_flow,
            "gps_hz_total": self._cnt_gps,
            "range_m": round(self._latest_range_m, 3) if self._latest_range_m is not None else None,
            "flow_quality": self._last_flow_quality,
            "adversary_preempted": self._adversary_active,
        }
        msg = String()
        msg.data = json.dumps(payload)
        self.status_pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SensorBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

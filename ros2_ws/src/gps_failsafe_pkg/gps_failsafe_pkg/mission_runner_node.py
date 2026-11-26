#!/usr/bin/env python3
"""Autonomous quadrotor mission runner for repeatable square, line, or hover flights.

Arms PX4, climbs to mission altitude, and flies a repeatable Offboard waypoint
trajectory via /fmu/in/trajectory_setpoint while publishing /mission/status.
"""

import argparse
import json
import math
import sys
import time
from typing import List, Tuple

from nav_msgs.msg import Odometry
from px4_msgs.msg import (
    EstimatorStatusFlags,
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleLocalPosition,
    VehicleStatus,
)
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Bool, String

from gps_failsafe_pkg.qos_profiles import px4_pub_qos, px4_sub_qos


Waypoint = Tuple[float, float, float, float]  # (N, E, D, yaw_rad)


def build_waypoints(pattern: str, size_m: float, altitude_m: float, loops: int) -> List[Waypoint]:
    """Generate repeatable NED waypoints for square, line, or hover missions."""
    z = -abs(altitude_m)
    if pattern == "hover":
        return [(0.0, 0.0, z, 0.0)]

    if pattern == "line":
        cycle = [
            (0.0, 0.0, z, 0.0),
            (size_m, 0.0, z, 0.0),
            (0.0, 0.0, z, math.pi),
        ]
    else:  # square
        half = size_m / 2.0
        cycle = [
            (0.0, 0.0, z, 0.0),
            (half, -half, z, 0.0),
            (half, half, z, math.pi / 2.0),
            (-half, half, z, math.pi),
            (-half, -half, z, -math.pi / 2.0),
            (0.0, 0.0, z, 0.0),
        ]

    waypoints: List[Waypoint] = []
    for _ in range(max(1, loops)):
        waypoints.extend(cycle)
    waypoints.append((0.0, 0.0, z, 0.0))
    return waypoints


class MissionRunnerNode(Node):
    """Publishes 20 Hz Offboard setpoints and sequences repeatable flight waypoints."""

    def __init__(
        self,
        pattern: str = "square",
        size_m: float = 12.0,
        altitude_m: float = 4.0,
        speed_mps: float = 2.0,
        loops: int = 2,
        hold_time_s: float = 2.0,
        land_on_finish: bool = True,
    ) -> None:
        super().__init__("mission_runner_node")

        self.pattern = pattern
        self.size_m = size_m
        self.altitude_m = altitude_m
        self.speed_mps = max(0.3, speed_mps)
        self.loops = loops
        self.hold_time_s = hold_time_s
        self.land_on_finish = land_on_finish

        self.waypoints = build_waypoints(pattern, size_m, altitude_m, loops)
        self.wp_idx = 0
        self.curr_target = [0.0, 0.0, -abs(altitude_m)]
        self.phase = "WAIT_READY"
        self.phase_enter_s = time.monotonic()
        self.wp_reached_s = None
        self.last_cmd_s = 0.0
        self.guardian_preempted = False

        self.lpos: VehicleLocalPosition | None = None
        self.vstatus: VehicleStatus | None = None
        self.flags: EstimatorStatusFlags | None = None
        self.gt_odom: Odometry | None = None

        sub_q = px4_sub_qos()
        pub_q = px4_pub_qos()

        self.create_subscription(
            VehicleLocalPosition, "/fmu/out/vehicle_local_position", self._on_lpos, sub_q
        )
        self.create_subscription(
            VehicleStatus, "/fmu/out/vehicle_status", self._on_vstatus, sub_q
        )
        self.create_subscription(
            EstimatorStatusFlags, "/fmu/out/estimator_status_flags", self._on_flags, sub_q
        )
        self.create_subscription(Odometry, "/uav/ground_truth_odom", self._on_gt, 10)
        self.create_subscription(Bool, "/guardian/failover_active", self._on_guardian, 10)

        self.pub_ocm = self.create_publisher(OffboardControlMode, "/fmu/in/offboard_control_mode", pub_q)
        self.pub_sp = self.create_publisher(TrajectorySetpoint, "/fmu/in/trajectory_setpoint", pub_q)
        self.pub_cmd = self.create_publisher(VehicleCommand, "/fmu/in/vehicle_command", pub_q)
        self.pub_status = self.create_publisher(String, "/mission/status", 10)

        self._dt = 0.05  # 20 Hz
        self.create_timer(self._dt, self._control_loop)
        self.create_timer(0.5, self._publish_status)

        self.get_logger().info(
            f"Mission initialized: pattern={pattern}, size={size_m}m, alt={altitude_m}m, "
            f"speed={speed_mps}m/s, waypoints={len(self.waypoints)}"
        )

    def _now_us(self) -> int:
        return int(self.get_clock().now().nanoseconds // 1000)

    def _on_lpos(self, msg: VehicleLocalPosition) -> None:
        self.lpos = msg

    def _on_vstatus(self, msg: VehicleStatus) -> None:
        self.vstatus = msg

    def _on_flags(self, msg: EstimatorStatusFlags) -> None:
        self.flags = msg

    def _on_gt(self, msg: Odometry) -> None:
        self.gt_odom = msg

    def _on_guardian(self, msg: Bool) -> None:
        if msg.data and not self.guardian_preempted:
            self.guardian_preempted = True
            self.phase = "GUARDIAN_HOLD"
            self.get_logger().warn("Guardian failover active! Mission runner yielding control.")

    def _send_command(self, command: int, p1: float = 0.0, p2: float = 0.0) -> None:
        msg = VehicleCommand()
        msg.timestamp = self._now_us()
        msg.command = command
        msg.param1 = float(p1)
        msg.param2 = float(p2)
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self.pub_cmd.publish(msg)

    def _publish_setpoint(self, n: float, e: float, d: float, yaw: float = float("nan")) -> None:
        ts = self._now_us()
        ocm = OffboardControlMode()
        ocm.timestamp = ts
        ocm.position = True
        self.pub_ocm.publish(ocm)

        sp = TrajectorySetpoint()
        sp.timestamp = ts
        sp.position = [float(n), float(e), float(d)]
        sp.yaw = float(yaw)
        self.pub_sp.publish(sp)

    def _step_toward(self, goal: Waypoint) -> float:
        """Smoothly advance curr_target toward goal at speed_mps; returns remaining distance."""
        dx = goal[0] - self.curr_target[0]
        dy = goal[1] - self.curr_target[1]
        dz = goal[2] - self.curr_target[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        max_step = self.speed_mps * self._dt
        if dist > max_step and dist > 1e-6:
            scale = max_step / dist
            self.curr_target[0] += dx * scale
            self.curr_target[1] += dy * scale
            self.curr_target[2] += dz * scale
        else:
            self.curr_target[0] = goal[0]
            self.curr_target[1] = goal[1]
            self.curr_target[2] = goal[2]
        return dist

    def _control_loop(self) -> None:
        now = time.monotonic()

        if self.phase == "GUARDIAN_HOLD":
            return

        if self.phase == "DONE":
            return

        if self.lpos is None or self.vstatus is None:
            return

        if self.phase == "WAIT_READY":
            self._publish_setpoint(0.0, 0.0, -abs(self.altitude_m))
            if self.vstatus.pre_flight_checks_pass and self.lpos.xy_valid and self.lpos.z_valid:
                if now - self.phase_enter_s > 1.5:
                    self.phase = "ARM_AND_OFFBOARD"
                    self.phase_enter_s = now
                    self.get_logger().info("Pre-flight checks passed; engaging Offboard & arming...")
            return

        if self.phase == "ARM_AND_OFFBOARD":
            self._publish_setpoint(0.0, 0.0, -abs(self.altitude_m))
            if now - self.last_cmd_s > 0.5:
                self.last_cmd_s = now
                if self.vstatus.nav_state != VehicleStatus.NAVIGATION_STATE_OFFBOARD:
                    self._send_command(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1.0, 6.0)
                if self.vstatus.arming_state != VehicleStatus.ARMING_STATE_ARMED:
                    self._send_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0)
            if (
                self.vstatus.arming_state == VehicleStatus.ARMING_STATE_ARMED
                and self.vstatus.nav_state == VehicleStatus.NAVIGATION_STATE_OFFBOARD
                and abs(self.lpos.z - (-abs(self.altitude_m))) < 0.8
            ):
                self.phase = "MISSION"
                self.phase_enter_s = now
                self.curr_target = [self.lpos.x, self.lpos.y, -abs(self.altitude_m)]
                self.get_logger().info("Takeoff complete! Starting waypoint mission.")
            return

        if self.phase == "MISSION":
            goal = self.waypoints[self.wp_idx]
            self._step_toward(goal)
            self._publish_setpoint(self.curr_target[0], self.curr_target[1], self.curr_target[2], 0.0)

            est_err = math.sqrt(
                (self.lpos.x - goal[0]) ** 2
                + (self.lpos.y - goal[1]) ** 2
                + (self.lpos.z - goal[2]) ** 2
            )
            if est_err < 0.75:
                if self.wp_reached_s is None:
                    self.wp_reached_s = now
                    self.get_logger().info(
                        f"Reached WP {self.wp_idx + 1}/{len(self.waypoints)}: "
                        f"target=({goal[0]:.1f},{goal[1]:.1f},{goal[2]:.1f})"
                    )
                elif now - self.wp_reached_s >= self.hold_time_s:
                    self.wp_reached_s = None
                    if self.wp_idx + 1 < len(self.waypoints):
                        self.wp_idx += 1
                    elif self.pattern == "hover":
                        self.wp_reached_s = now
                    elif self.land_on_finish:
                        self.phase = "LANDING"
                        self.phase_enter_s = now
                        self._send_command(VehicleCommand.VEHICLE_CMD_NAV_LAND)
                        self.get_logger().info("Mission waypoints finished; commanding AUTO LAND.")
                    else:
                        self.wp_reached_s = now
            else:
                self.wp_reached_s = None
            return

        if self.phase == "LANDING":
            if now - self.last_cmd_s > 1.0:
                self.last_cmd_s = now
                if self.vstatus.nav_state != VehicleStatus.NAVIGATION_STATE_AUTO_LAND:
                    self._send_command(VehicleCommand.VEHICLE_CMD_NAV_LAND)
            if self.vstatus.arming_state == VehicleStatus.ARMING_STATE_DISARMED:
                self.phase = "DONE"
                self.get_logger().info("Landed and disarmed cleanly.")

    def _publish_status(self) -> None:
        goal = self.waypoints[min(self.wp_idx, len(self.waypoints) - 1)]
        gt = self.gt_odom.pose.pose.position if self.gt_odom else None
        payload = {
            "phase": self.phase,
            "pattern": self.pattern,
            "wp_index": self.wp_idx,
            "wp_total": len(self.waypoints),
            "target_ned": [round(float(x), 2) for x in self.curr_target],
            "goal_ned": [round(float(goal[0]), 2), round(float(goal[1]), 2), round(float(goal[2]), 2)],
            "est_ned": [round(self.lpos.x, 2), round(self.lpos.y, 2), round(self.lpos.z, 2)] if self.lpos else None,
            "gt_ned": [round(gt.x, 2), round(gt.y, 2), round(gt.z, 2)] if gt else None,
            "cs_gps": bool(self.flags.cs_gps) if self.flags else None,
            "cs_opt_flow": bool(self.flags.cs_opt_flow) if self.flags else None,
            "arming_state": int(self.vstatus.arming_state) if self.vstatus else None,
            "nav_state": int(self.vstatus.nav_state) if self.vstatus else None,
        }
        msg = String()
        msg.data = json.dumps(payload)
        self.pub_status.publish(msg)


def parse_cli_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PX4 Offboard autonomous waypoint mission runner")
    parser.add_argument("--pattern", choices=["square", "line", "hover"], default="square")
    parser.add_argument("--size", type=float, default=12.0, help="Square side or line length [m]")
    parser.add_argument("--altitude", type=float, default=4.0, help="Flight altitude AGL [m]")
    parser.add_argument("--speed", type=float, default=2.0, help="Setpoint cruise speed [m/s]")
    parser.add_argument("--loops", type=int, default=2, help="Number of mission pattern loops")
    parser.add_argument("--hold-time", type=float, default=1.5, help="Wait time at each waypoint [s]")
    parser.add_argument("--no-land", action="store_true", help="Hold final hover instead of landing")
    known, _ = parser.parse_known_args(argv)
    return known


def main(args=None) -> None:
    cli = parse_cli_args(sys.argv[1:])
    rclpy.init(args=args)
    node = MissionRunnerNode(
        pattern=cli.pattern,
        size_m=cli.size,
        altitude_m=cli.altitude,
        speed_mps=cli.speed,
        loops=cli.loops,
        hold_time_s=cli.hold_time,
        land_on_finish=not cli.no_land,
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

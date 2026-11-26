"""Shared ROS 2 QoS profiles compatible with PX4 uXRCE-DDS topics."""

from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy


def px4_sub_qos(depth: int = 5) -> QoSProfile:
    """Best-effort volatile subscriber QoS matching PX4 /fmu/out/* publishers."""
    return QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
    )


def px4_pub_qos(depth: int = 5) -> QoSProfile:
    """Best-effort volatile publisher QoS for PX4 /fmu/in/* topics."""
    return QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
    )

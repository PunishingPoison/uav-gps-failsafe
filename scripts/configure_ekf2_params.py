#!/usr/bin/env python3
"""Configure and verify PX4 EKF2 sensor aiding parameters via pymavlink.

Note: PX4's MAVLink parameter protocol encodes integer parameters (MAV_PARAM_TYPE_INT32)
via raw 32-bit bit-reinterpretation inside the float32 `param_value` wire field
(memcpy / C union), rather than numeric float conversion.
"""

import argparse
import struct
import sys
import time
from typing import Dict, Tuple, Union

from pymavlink import mavutil


NOMINAL_PARAMS: Dict[str, Tuple[Union[int, float], int]] = {
    "EKF2_GPS_CTRL": (7, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
    "EKF2_OF_CTRL": (1, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
    "EKF2_RNG_CTRL": (2, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
    "EKF2_HGT_REF": (1, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
    "EKF2_TERR_MASK": (3, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
    "EKF2_OF_QMIN": (1, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
    "MAV_USEHILGPS": (1, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
}

GPS_DENIED_PARAMS: Dict[str, Tuple[Union[int, float], int]] = {
    "EKF2_GPS_CTRL": (0, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
    "EKF2_OF_CTRL": (1, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
    "EKF2_RNG_CTRL": (2, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
    "EKF2_HGT_REF": (2, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
}


def encode_param_value(value: Union[int, float], param_type: int) -> float:
    """Encode an int32 or real32 value into MAVLink wire float32."""
    if param_type == mavutil.mavlink.MAV_PARAM_TYPE_INT32:
        return struct.unpack("<f", struct.pack("<i", int(value)))[0]
    return float(value)


def decode_param_value(wire_value: float, param_type: int) -> Union[int, float]:
    """Decode a MAVLink wire float32 into Python int or float based on param_type."""
    if param_type == mavutil.mavlink.MAV_PARAM_TYPE_INT32:
        return struct.unpack("<i", struct.pack("<f", float(wire_value)))[0]
    return float(wire_value)


def connect_px4(mavlink_url: str, timeout: float = 25.0) -> mavutil.mavfile:
    conn = mavutil.mavlink_connection(mavlink_url)
    hb = conn.wait_heartbeat(timeout=timeout)
    if hb is None:
        raise TimeoutError(f"No PX4 heartbeat received on {mavlink_url} within {timeout}s")
    return conn


def read_param(conn: mavutil.mavfile, name: str, timeout: float = 3.0) -> Union[int, float]:
    conn.mav.param_request_read_send(
        conn.target_system,
        conn.target_component,
        name.encode("ascii"),
        -1,
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        msg = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
        if msg is None:
            continue
        pid = msg.param_id.rstrip("\x00")
        if pid == name:
            return decode_param_value(msg.param_value, msg.param_type)
    raise TimeoutError(f"Timed out reading parameter {name}")


def set_param_verified(
    conn: mavutil.mavfile,
    name: str,
    value: Union[int, float],
    param_type: int,
    retries: int = 3,
    force: bool = False,
) -> Union[int, float]:
    if not force:
        try:
            curr = read_param(conn, name, timeout=1.0)
            if abs(float(curr) - float(value)) < 1e-4:
                return curr
        except TimeoutError:
            pass

    wire_val = encode_param_value(value, param_type)
    for attempt in range(1, retries + 1):
        conn.mav.param_set_send(
            conn.target_system,
            conn.target_component,
            name.encode("ascii"),
            wire_val,
            param_type,
        )
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline:
            msg = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
            if msg is None:
                continue
            pid = msg.param_id.rstrip("\x00")
            if pid == name:
                got = decode_param_value(msg.param_value, msg.param_type)
                if abs(float(got) - float(value)) < 1e-4:
                    return got
        if attempt < retries:
            time.sleep(0.15)
    raise RuntimeError(f"Failed to verify {name}={value}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure PX4 EKF2 multi-sensor parameters")
    parser.add_argument("--url", default="udpin:0.0.0.0:14540", help="pymavlink connection string")
    parser.add_argument(
        "--mode",
        choices=["nominal", "gps-denied", "status"],
        default="nominal",
        help="nominal (GPS+OF+LiDAR), gps-denied (OF+LiDAR only), or status (read-only)",
    )
    parser.add_argument("--force", action="store_true", help="Force PARAM_SET even if already equal")
    args = parser.parse_args()

    conn = connect_px4(args.url)
    print(f"[EKF2] Connected to PX4 sys={conn.target_system} comp={conn.target_component} via {args.url}")

    if args.mode == "status":
        for name in NOMINAL_PARAMS:
            val = read_param(conn, name)
            print(f"  {name:18s} = {val}")
        return 0

    targets = NOMINAL_PARAMS if args.mode == "nominal" else GPS_DENIED_PARAMS
    print(f"[EKF2] Applying mode '{args.mode}':")
    for name, (val, ptype) in targets.items():
        actual = set_param_verified(conn, name, val, ptype, force=args.force)
        print(f"  {name:18s} -> {actual} (verified)")

    return 0


if __name__ == "__main__":
    sys.exit(main())

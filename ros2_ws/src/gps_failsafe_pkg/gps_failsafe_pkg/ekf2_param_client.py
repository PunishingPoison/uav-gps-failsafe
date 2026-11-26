#!/usr/bin/env python3
"""Shared PX4 MAVLink parameter helper using C-union INT32 bit-reinterpretation."""

import struct
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

# Ordered so GPS fusion is disabled first during emergency cutover
GPS_DENIED_PARAMS: Dict[str, Tuple[Union[int, float], int]] = {
    "EKF2_GPS_CTRL": (0, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
    "EKF2_HGT_REF": (2, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
    "EKF2_OF_CTRL": (1, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
    "EKF2_RNG_CTRL": (2, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
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
    """Open MAVLink UDP link and block until a PX4 heartbeat arrives."""
    conn = mavutil.mavlink_connection(mavlink_url)
    hb = conn.wait_heartbeat(timeout=timeout)
    if hb is None:
        raise TimeoutError(f"No PX4 heartbeat received on {mavlink_url} within {timeout}s")
    return conn


def drain_mavlink_rx(conn: mavutil.mavfile, max_msgs: int = 256) -> None:
    """Flush queued incoming MAVLink packets so parameter acks are read cleanly."""
    for _ in range(max_msgs):
        if conn.recv_match(blocking=False) is None:
            break


def read_param(conn: mavutil.mavfile, name: str, timeout: float = 3.0) -> Union[int, float]:
    drain_mavlink_rx(conn)
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
    check_first: bool = True,
) -> Union[int, float]:
    """Send PARAM_SET and verify PX4 PARAM_VALUE echo matches requested value."""
    drain_mavlink_rx(conn)
    if not force and check_first:
        try:
            curr = read_param(conn, name, timeout=0.8)
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
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            msg = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.3)
            if msg is None:
                continue
            pid = msg.param_id.rstrip("\x00")
            if pid == name:
                got = decode_param_value(msg.param_value, msg.param_type)
                if abs(float(got) - float(value)) < 1e-4:
                    return got
        if attempt < retries:
            time.sleep(0.08)
    raise RuntimeError(f"Failed to verify {name}={value}")


def apply_ekf2_mode(
    conn: mavutil.mavfile,
    mode: str,
    force: bool = False,
    fast_cutover: bool = False,
) -> Dict[str, Union[int, float]]:
    """Apply nominal or gps-denied EKF2 parameter set and return verified readbacks."""
    targets = NOMINAL_PARAMS if mode == "nominal" else GPS_DENIED_PARAMS
    results: Dict[str, Union[int, float]] = {}
    for name, (val, ptype) in targets.items():
        results[name] = set_param_verified(
            conn,
            name,
            val,
            ptype,
            force=force,
            check_first=not fast_cutover,
        )
    return results

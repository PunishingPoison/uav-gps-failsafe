#!/usr/bin/env python3
"""Configure and verify PX4 EKF2 sensor aiding parameters via pymavlink."""

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
PKG_PARENT = REPO_ROOT / "ros2_ws" / "src" / "gps_failsafe_pkg"
if str(PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(PKG_PARENT))

from gps_failsafe_pkg.ekf2_param_client import (  # noqa: E402
    NOMINAL_PARAMS,
    apply_ekf2_mode,
    connect_px4,
    read_param,
)


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

    print(f"[EKF2] Applying mode '{args.mode}':")
    results = apply_ekf2_mode(conn, args.mode, force=args.force)
    for name, actual in results.items():
        print(f"  {name:18s} -> {actual} (verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

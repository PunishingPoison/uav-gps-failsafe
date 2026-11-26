#!/usr/bin/env python3
"""Automated multi-episode dataset collector for PX4 SITL GPS spoofing experiments.

Runs independent headless simulation episodes across nominal maneuvers (hover, line, square)
and all three spoofing profiles (step, drift, takeover) with varied parameters/bearings,
recording synchronized 20 Hz CSVs into data/raw/.
"""

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import List


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTAINER_NAME = "uav_gps_failsafe_sim"


@dataclass
class EpisodeSpec:
    episode_id: str
    split_hint: str  # "train" or "test"
    pattern: str
    speed_mps: float
    size_m: float
    altitude_m: float
    pre_attack_s: float
    phase2_s: float
    attack_mode: str  # "none", "step", "drift", "takeover"
    rate_mps: float = 0.0
    bearing_deg: float = 0.0
    offset_n: float = 0.0
    offset_e: float = 0.0
    ramp_s: float = 2.5


EPISODES: List[EpisodeSpec] = [
    # --- Pure Nominal Flights (zero spoofing; includes sharp turns & reversals) ---
    EpisodeSpec("ep_nom_01_hover", "train", "hover", 1.5, 10.0, 4.0, 10.0, 12.0, "none"),
    EpisodeSpec("ep_nom_02_square_norm", "train", "square", 2.0, 12.0, 4.0, 10.0, 14.0, "none"),
    EpisodeSpec("ep_nom_03_line_rev", "train", "line", 2.5, 12.0, 4.5, 10.0, 14.0, "none"),
    EpisodeSpec("ep_nom_04_square_fast", "test", "square", 2.8, 14.0, 4.0, 10.0, 14.0, "none"),
    # --- Step Spoofing Attacks (sub-gate immediate EKF2 fusion + super-gate jump) ---
    EpisodeSpec("ep_step_01_4m_n", "train", "hover", 2.0, 10.0, 4.0, 8.0, 13.0, "step", offset_n=4.0, offset_e=0.0),
    EpisodeSpec("ep_step_02_3p5m_diag", "train", "square", 2.0, 12.0, 4.0, 8.0, 13.0, "step", offset_n=2.6, offset_e=-2.6),
    EpisodeSpec("ep_step_03_12m_spike", "train", "line", 2.0, 12.0, 4.0, 8.0, 16.0, "step", offset_n=12.0, offset_e=0.0),
    EpisodeSpec("ep_step_04_3p8m_e", "test", "square", 2.2, 12.0, 4.0, 8.0, 13.0, "step", offset_n=0.0, offset_e=3.8),
    # --- Slow Drift / Meaconing Attacks ---
    EpisodeSpec("ep_drift_01_0p8mps", "train", "square", 2.0, 12.0, 4.0, 8.0, 14.0, "drift", rate_mps=0.8, bearing_deg=0.0),
    EpisodeSpec("ep_drift_02_1p8mps_sw", "train", "line", 2.2, 12.0, 4.5, 8.0, 13.0, "drift", rate_mps=1.8, bearing_deg=225.0),
    EpisodeSpec("ep_drift_03_2p5mps_e", "train", "hover", 2.0, 10.0, 4.0, 8.0, 12.0, "drift", rate_mps=2.5, bearing_deg=90.0),
    EpisodeSpec("ep_drift_04_1p2mps_nw", "test", "square", 2.2, 12.0, 4.0, 8.0, 14.0, "drift", rate_mps=1.2, bearing_deg=315.0),
    # --- Smooth Coordinated Takeover Attacks ---
    EpisodeSpec("ep_take_01_1p2mps", "train", "hover", 2.0, 10.0, 4.0, 8.0, 14.0, "takeover", rate_mps=1.2, bearing_deg=45.0, ramp_s=3.0),
    EpisodeSpec("ep_take_02_2p5mps", "train", "square", 2.0, 12.0, 4.0, 8.0, 13.0, "takeover", rate_mps=2.5, bearing_deg=180.0, ramp_s=2.0),
    EpisodeSpec("ep_take_03_3p0mps_ne", "train", "line", 2.2, 12.0, 4.5, 8.0, 12.0, "takeover", rate_mps=3.0, bearing_deg=225.0, ramp_s=1.8),
    EpisodeSpec("ep_take_04_1p6mps_se", "test", "square", 2.2, 12.0, 4.0, 8.0, 14.0, "takeover", rate_mps=1.6, bearing_deg=135.0, ramp_s=2.5),
]


def run_episode(spec: EpisodeSpec, out_csv: Path, build_pkg: bool, host_uid: int, host_gid: int) -> None:
    """Launch a fresh headless SITL run and record one complete episode CSV."""
    print(f"\n[COLLECT] === Starting {spec.episode_id} (mode={spec.attack_mode}, split={spec.split_hint}) ===", flush=True)
    subprocess.run([str(REPO_ROOT / "scripts" / "run_simulation.sh"), "--headless", "--detach"], check=True)

    try:
        adv_cmd: List[str] = []
        if spec.attack_mode != "none":
            adv_cmd = [
                "/uav_ws/ros2_ws/install/gps_failsafe_pkg/lib/gps_failsafe_pkg/adversary_spoofer_node",
                "--mode",
                spec.attack_mode,
                "--rate-mps",
                str(spec.rate_mps),
                "--bearing-deg",
                str(spec.bearing_deg),
                "--offset-n",
                str(spec.offset_n),
                "--offset-e",
                str(spec.offset_e),
                "--ramp-s",
                str(spec.ramp_s),
            ]

        build_step = (
            "cd /uav_ws/ros2_ws && colcon build --symlink-install --packages-select gps_failsafe_pkg && "
            if build_pkg
            else ""
        )

        spec_json = json.dumps(asdict(spec))
        adv_json = json.dumps(adv_cmd)
        container_out = f"/uav_ws/data/raw/{out_csv.name}"

        inner = f"""
set -e
source /opt/ros/jazzy/setup.bash
{build_step}source /uav_ws/ros2_ws/install/setup.bash

python3 - << 'PY'
import json, os, signal, subprocess, time
import rclpy
from std_msgs.msg import String

spec = json.loads({spec_json!r})
adv_cmd = json.loads({adv_json!r})

rclpy.init()
node = rclpy.create_node("episode_orchestrator")
state = {{"mission": None}}
node.create_subscription(String, "/mission/status", lambda m: state.__setitem__("mission", json.loads(m.data)), 10)

MISSION_BIN = "/uav_ws/ros2_ws/install/gps_failsafe_pkg/lib/gps_failsafe_pkg/mission_runner_node"
LOGGER_BIN = "/uav_ws/ros2_ws/install/gps_failsafe_pkg/lib/gps_failsafe_pkg/telemetry_logger_node"

def kill_proc(p):
    if p and p.poll() is None:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        p.wait(timeout=6)

def spin_for(sec):
    t0 = time.monotonic()
    while time.monotonic() - t0 < sec:
        rclpy.spin_once(node, timeout_sec=0.05)

lproc = subprocess.Popen(
    [LOGGER_BIN, "--output", "{container_out}", "--episode-id", spec["episode_id"], "--rate-hz", "20.0"],
    preexec_fn=os.setsid,
)
mproc = subprocess.Popen(
    [
        MISSION_BIN,
        "--pattern", spec["pattern"],
        "--size", str(spec["size_m"]),
        "--altitude", str(spec["altitude_m"]),
        "--speed", str(spec["speed_mps"]),
        "--loops", "4",
        "--hold-time", "1.0",
        "--no-land",
    ],
    preexec_fn=os.setsid,
)

# Wait for takeoff & MISSION start (up to 40s)
t0 = time.monotonic()
entered = False
while time.monotonic() - t0 < 40.0:
    spin_for(0.2)
    m = state["mission"]
    if m and m.get("phase") == "MISSION":
        entered = True
        break
if not entered:
    kill_proc(mproc)
    kill_proc(lproc)
    raise RuntimeError(f"Episode {{spec['episode_id']}} timed out waiting for MISSION phase")

# Nominal phase before attack
spin_for(float(spec["pre_attack_s"]))

aproc = None
if adv_cmd:
    aproc = subprocess.Popen(adv_cmd, preexec_fn=os.setsid)

spin_for(float(spec["phase2_s"]))

kill_proc(aproc)
kill_proc(mproc)
kill_proc(lproc)
rclpy.shutdown()
PY
chown {host_uid}:{host_gid} "{container_out}"
"""
        subprocess.run(["docker", "exec", CONTAINER_NAME, "bash", "-c", inner], check=True)
    finally:
        subprocess.run([str(REPO_ROOT / "scripts" / "run_simulation.sh"), "--stop"], check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect multi-episode PX4 SITL dataset")
    parser.add_argument("--out-dir", default=str(REPO_ROOT / "data" / "raw"))
    parser.add_argument("--force", action="store_true", help="Re-record even if CSV already exists")
    parser.add_argument("--only", nargs="*", default=None, help="Optional subset of episode_ids to run")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    uid, gid = os.getuid(), os.getgid()

    selected = [e for e in EPISODES if (not args.only or e.episode_id in args.only)]
    manifest = []
    did_build = False

    t_all = time.monotonic()
    for spec in selected:
        out_csv = out_dir / f"{spec.episode_id}.csv"
        if out_csv.exists() and not args.force:
            line_cnt = sum(1 for _ in open(out_csv, encoding="utf-8"))
            if line_cnt >= 150:
                print(f"[COLLECT] Skipping existing {spec.episode_id}.csv ({line_cnt} lines)", flush=True)
                manifest.append({**asdict(spec), "csv": out_csv.name, "lines": line_cnt})
                continue

        run_episode(spec, out_csv, build_pkg=(not did_build), host_uid=uid, host_gid=gid)
        did_build = True
        line_cnt = sum(1 for _ in open(out_csv, encoding="utf-8"))
        print(f"[COLLECT] Saved {out_csv.name} ({line_cnt} lines)", flush=True)
        manifest.append({**asdict(spec), "csv": out_csv.name, "lines": line_cnt})

    manifest_path = out_dir / "dataset_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n[COLLECT] Completed {len(manifest)} episodes in {time.monotonic() - t_all:.1f}s -> {manifest_path}")


if __name__ == "__main__":
    main()

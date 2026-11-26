#!/usr/bin/env python3
"""Automated ablation suite comparing Unguarded vs AI-Guardian UAV flights.

Runs independent headless PX4 SITL + Gazebo Harmonic experiments across Step,
Slow Drift (multiple drift rates), Coordinated Takeover, and Fast Nominal
baseline, saving both 20 Hz synchronized ROS telemetry CSVs and raw PX4 binary
.ulg flight logs into data/experiments/.
"""

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import subprocess
import time
from typing import List


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTAINER_NAME = "uav_gps_failsafe_sim"


@dataclass
class ExperimentSpec:
    run_id: str
    guardian: bool
    attack_mode: str  # "none", "step", "drift", "takeover"
    pattern: str = "square"
    speed_mps: float = 2.0
    size_m: float = 12.0
    altitude_m: float = 4.0
    pre_attack_s: float = 6.0
    eval_s: float = 12.0
    rate_mps: float = 0.0
    bearing_deg: float = 0.0
    offset_n: float = 0.0
    offset_e: float = 0.0
    ramp_s: float = 2.0
    model: str = "rf"


EXPERIMENTS: List[ExperimentSpec] = [
    ExperimentSpec("exp_nominal_guarded", guardian=True, attack_mode="none", speed_mps=2.5, pre_attack_s=4.0, eval_s=14.0),
    ExperimentSpec("exp_step_unguarded", guardian=False, attack_mode="step", offset_n=4.0),
    ExperimentSpec("exp_step_guarded", guardian=True, attack_mode="step", offset_n=4.0),
    ExperimentSpec("exp_drift_0p8_unguarded", guardian=False, attack_mode="drift", rate_mps=0.8, bearing_deg=45.0),
    ExperimentSpec("exp_drift_0p8_guarded", guardian=True, attack_mode="drift", rate_mps=0.8, bearing_deg=45.0),
    ExperimentSpec("exp_drift_1p5_guarded", guardian=True, attack_mode="drift", rate_mps=1.5, bearing_deg=45.0),
    ExperimentSpec("exp_drift_2p2_unguarded", guardian=False, attack_mode="drift", rate_mps=2.2, bearing_deg=45.0),
    ExperimentSpec("exp_drift_2p2_guarded", guardian=True, attack_mode="drift", rate_mps=2.2, bearing_deg=45.0),
    ExperimentSpec("exp_takeover_unguarded", guardian=False, attack_mode="takeover", rate_mps=2.2, bearing_deg=180.0, ramp_s=2.0),
    ExperimentSpec("exp_takeover_guarded", guardian=True, attack_mode="takeover", rate_mps=2.2, bearing_deg=180.0, ramp_s=2.0),
]


def run_single(spec: ExperimentSpec, out_dir: Path, build_pkg: bool, host_uid: int, host_gid: int) -> None:
    print(f"\n[EXP] === Starting {spec.run_id} (guardian={spec.guardian}, mode={spec.attack_mode}) ===", flush=True)
    subprocess.run([str(REPO_ROOT / "scripts" / "run_simulation.sh"), "--headless", "--detach"], check=True)

    try:
        build_step = (
            "cd /uav_ws/ros2_ws && colcon build --symlink-install --packages-select gps_failsafe_pkg && "
            f"chown -R {host_uid}:{host_gid} build install log && "
            if build_pkg
            else ""
        )

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

        spec_json = json.dumps(asdict(spec))
        adv_json = json.dumps(adv_cmd)
        out_csv = f"/uav_ws/data/experiments/{spec.run_id}.csv"
        out_ulg = f"/uav_ws/data/experiments/{spec.run_id}.ulg"

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
node = rclpy.create_node("exp_orchestrator")
state = {{"mis": None, "grd": None}}
node.create_subscription(String, "/mission/status", lambda m: state.__setitem__("mis", json.loads(m.data)), 10)
node.create_subscription(String, "/guardian/status", lambda m: state.__setitem__("grd", json.loads(m.data)), 10)

MISSION_BIN = "/uav_ws/ros2_ws/install/gps_failsafe_pkg/lib/gps_failsafe_pkg/mission_runner_node"
LOGGER_BIN = "/uav_ws/ros2_ws/install/gps_failsafe_pkg/lib/gps_failsafe_pkg/telemetry_logger_node"
GUARDIAN_BIN = "/uav_ws/ros2_ws/install/gps_failsafe_pkg/lib/gps_failsafe_pkg/guardian_ai_node"

def kill_proc(p):
    if p and p.poll() is None:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        p.wait(timeout=6)

def spin_for(sec):
    t0 = time.monotonic()
    while time.monotonic() - t0 < sec:
        rclpy.spin_once(node, timeout_sec=0.05)

lproc = subprocess.Popen([LOGGER_BIN, "--output", "{out_csv}", "--episode-id", spec["run_id"], "--rate-hz", "20.0"], preexec_fn=os.setsid)
gproc = None
if spec["guardian"]:
    gproc = subprocess.Popen([GUARDIAN_BIN, "--model", spec["model"]], preexec_fn=os.setsid)

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

t0 = time.monotonic()
ready = False
while time.monotonic() - t0 < 40.0:
    spin_for(0.2)
    m = state["mis"]
    g = state["grd"]
    grd_ok = (not spec["guardian"]) or (g and g.get("guardian_monitoring"))
    if m and m.get("phase") == "MISSION" and grd_ok:
        ready = True
        break
if not ready:
    kill_proc(mproc); kill_proc(gproc); kill_proc(lproc)
    raise RuntimeError(f"Experiment {{spec['run_id']}} timed out waiting for MISSION + Guardian readiness")

spin_for(float(spec["pre_attack_s"]))
aproc = subprocess.Popen(adv_cmd, preexec_fn=os.setsid) if adv_cmd else None
spin_for(float(spec["eval_s"]))

kill_proc(aproc)
kill_proc(mproc)
kill_proc(gproc)
kill_proc(lproc)
rclpy.shutdown()
PY

# Copy raw PX4 ULog generated during this flight
ULG_SRC=$(find /opt/PX4-Autopilot/build/px4_sitl_default/log -name '*.ulg' -type f | sort | tail -n 1)
if [[ -n "$ULG_SRC" && -f "$ULG_SRC" ]]; then
  cp "$ULG_SRC" "{out_ulg}"
  chown {host_uid}:{host_gid} "{out_ulg}"
fi
chown {host_uid}:{host_gid} "{out_csv}"
"""
        subprocess.run(["docker", "exec", CONTAINER_NAME, "bash", "-c", inner], check=True)
    finally:
        subprocess.run([str(REPO_ROOT / "scripts" / "run_simulation.sh"), "--stop"], check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run paired Unguarded vs AI-Guardian experiments")
    parser.add_argument("--out-dir", default=str(REPO_ROOT / "data" / "experiments"))
    parser.add_argument("--force", action="store_true", help="Re-run even if outputs exist")
    parser.add_argument("--only", nargs="*", default=None, help="Subset of run_ids to execute")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    uid, gid = os.getuid(), os.getgid()

    selected = [e for e in EXPERIMENTS if (not args.only or e.run_id in args.only)]
    manifest = []
    did_build = False

    t_start = time.monotonic()
    for spec in selected:
        csv_p = out_dir / f"{spec.run_id}.csv"
        ulg_p = out_dir / f"{spec.run_id}.ulg"
        if csv_p.exists() and not args.force:
            line_cnt = sum(1 for _ in open(csv_p, encoding="utf-8"))
            if line_cnt >= 150:
                print(f"[EXP] Skipping existing {csv_p.name} ({line_cnt} lines)", flush=True)
                manifest.append({**asdict(spec), "csv": csv_p.name, "ulg": ulg_p.name if ulg_p.exists() else None, "lines": line_cnt})
                continue

        run_single(spec, out_dir, build_pkg=(not did_build), host_uid=uid, host_gid=gid)
        did_build = True
        line_cnt = sum(1 for _ in open(csv_p, encoding="utf-8"))
        print(f"[EXP] Saved {csv_p.name} ({line_cnt} lines) & ulg={ulg_p.exists()}", flush=True)
        manifest.append({**asdict(spec), "csv": csv_p.name, "ulg": ulg_p.name if ulg_p.exists() else None, "lines": line_cnt})

    manifest_path = out_dir / "experiments_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n[EXP] Completed {len(manifest)} experiments in {time.monotonic() - t_start:.1f}s -> {manifest_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

MODE="drift"
RATE="2.0"
BEARING="45.0"
OFFSET_N="4.0"
OFFSET_E="0.0"
GUARDIAN="on"
MODEL="rf"
PRE_S="10"
DEMO_S="18"
HEADLESS=0
LAUNCH_QGC=0
KEEP_SIM=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)      MODE="$2"; shift 2 ;;
    --rate)      RATE="$2"; shift 2 ;;
    --bearing)   BEARING="$2"; shift 2 ;;
    --offset-n)  OFFSET_N="$2"; shift 2 ;;
    --offset-e)  OFFSET_E="$2"; shift 2 ;;
    --guardian)  GUARDIAN="$2"; shift 2 ;;
    --model)     MODEL="$2"; shift 2 ;;
    --pre-s)     PRE_S="$2"; shift 2 ;;
    --demo-s)    DEMO_S="$2"; shift 2 ;;
    --headless)  HEADLESS=1; shift ;;
    --qgc)       LAUNCH_QGC=1; shift ;;
    --keep)      KEEP_SIM=1; shift ;;
    -h|--help)
      cat <<EOF
Usage: $0 [options]
  --mode <step|drift|takeover>   Spoofing profile (default: drift)
  --rate <m/s>                   Drift/takeover speed (default: 2.0)
  --bearing <deg>                Spoofing bearing (default: 45.0)
  --offset-n <m>                 Step North offset (default: 4.0)
  --offset-e <m>                 Step East offset (default: 0.0)
  --guardian <on|off>            Enable AI Guardian auto-recovery (default: on)
  --model <rf|xgb>               Classifier (default: rf)
  --pre-s <sec>                  Nominal flight before attack (default: 10)
  --demo-s <sec>                 Post-attack observation window (default: 18)
  --qgc                          Launch QGroundControl alongside Gazebo GUI
  --headless                     Run Gazebo without GUI window
  --keep                         Keep simulation container alive after demo ends
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

QGC_PID=""
cleanup() {
  if [[ -n "$QGC_PID" ]]; then
    kill "$QGC_PID" >/dev/null 2>&1 || true
  fi
  if [[ "$KEEP_SIM" -eq 0 ]]; then
    "${SCRIPT_DIR}/run_simulation.sh" --stop >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

echo "[DEMO] Launching PX4 SITL + Gazebo Harmonic (headless=${HEADLESS})..."
if [[ "$HEADLESS" -eq 1 ]]; then
  "${SCRIPT_DIR}/run_simulation.sh" --headless --detach
else
  "${SCRIPT_DIR}/run_simulation.sh" --detach
fi

if [[ "$LAUNCH_QGC" -eq 1 ]]; then
  if [[ -x "/home/vcmr/Downloads/squashfs-root/AppRun" ]]; then
    /home/vcmr/Downloads/squashfs-root/AppRun >/tmp/qgc_demo.log 2>&1 &
    QGC_PID=$!
    echo "[DEMO] QGroundControl started (PID=$QGC_PID)."
  elif command -v QGroundControl >/dev/null 2>&1; then
    QGroundControl >/tmp/qgc_demo.log 2>&1 &
    QGC_PID=$!
    echo "[DEMO] QGroundControl started (PID=$QGC_PID)."
  else
    echo "[DEMO] QGroundControl binary not found; continuing with Gazebo + terminal monitor."
  fi
fi

docker exec uav_gps_failsafe_sim bash -c "
set -e
source /opt/ros/jazzy/setup.bash
source /uav_ws/ros2_ws/install/setup.bash

python3 - << 'PY'
import json, math, os, signal, subprocess, time
import rclpy
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from px4_msgs.msg import VehicleLocalPosition, EstimatorStatusFlags, VehicleStatus

MODE = '${MODE}'
RATE = '${RATE}'
BEARING = '${BEARING}'
OFFSET_N = '${OFFSET_N}'
OFFSET_E = '${OFFSET_E}'
GUARDIAN = '${GUARDIAN}' == 'on'
MODEL = '${MODEL}'
PRE_S = float('${PRE_S}')
DEMO_S = float('${DEMO_S}')

rclpy.init()
node = rclpy.create_node('demo_orchestrator')
qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=5)
st = {'lp': None, 'gt': None, 'fl': None, 'vs': None, 'mis': None, 'grd': None}
node.create_subscription(VehicleLocalPosition, '/fmu/out/vehicle_local_position', lambda m: st.__setitem__('lp', m), qos)
node.create_subscription(Odometry, '/uav/ground_truth_odom', lambda m: st.__setitem__('gt', m), qos)
node.create_subscription(EstimatorStatusFlags, '/fmu/out/estimator_status_flags', lambda m: st.__setitem__('fl', m), qos)
node.create_subscription(VehicleStatus, '/fmu/out/vehicle_status', lambda m: st.__setitem__('vs', m), qos)
node.create_subscription(String, '/mission/status', lambda m: st.__setitem__('mis', json.loads(m.data)), 10)
node.create_subscription(String, '/guardian/status', lambda m: st.__setitem__('grd', json.loads(m.data)), 10)

MISSION_BIN = '/uav_ws/ros2_ws/install/gps_failsafe_pkg/lib/gps_failsafe_pkg/mission_runner_node'
GUARDIAN_BIN = '/uav_ws/ros2_ws/install/gps_failsafe_pkg/lib/gps_failsafe_pkg/guardian_ai_node'
ADV_BIN = '/uav_ws/ros2_ws/install/gps_failsafe_pkg/lib/gps_failsafe_pkg/adversary_spoofer_node'

def kill_proc(p):
    if p and p.poll() is None:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        p.wait(timeout=5)

def spin_for(sec):
    t0 = time.monotonic()
    while time.monotonic() - t0 < sec:
        rclpy.spin_once(node, timeout_sec=0.05)

gproc = subprocess.Popen([GUARDIAN_BIN, '--model', MODEL], preexec_fn=os.setsid) if GUARDIAN else None
mproc = subprocess.Popen([MISSION_BIN, '--pattern', 'square', '--size', '12.0', '--altitude', '4.0', '--speed', '2.0', '--loops', '4', '--no-land'], preexec_fn=os.setsid)

print('[DEMO] Waiting for takeoff & mission start...', flush=True)
t0 = time.monotonic()
while time.monotonic() - t0 < 40.0:
    spin_for(0.2)
    m = st['mis']; g = st['grd']
    if m and m.get('phase') == 'MISSION' and ((not GUARDIAN) or (g and g.get('guardian_monitoring'))):
        break

print(f'[DEMO] Nominal square flight active for {PRE_S:.0f}s (guardian={GUARDIAN}, model={MODEL})...', flush=True)
t_end_pre = time.monotonic() + PRE_S
next_print = time.monotonic()
while time.monotonic() < t_end_pre:
    spin_for(0.1)
    if time.monotonic() >= next_print and st['lp'] and st['gt']:
        next_print += 2.0
        lp, gt, g, fl, vs = st['lp'], st['gt'], st['grd'], st['fl'], st['vs']
        gp = gt.pose.pose.position
        err = math.hypot(lp.x - gp.x, lp.y - gp.y)
        prob = g.get('spoof_prob') if g else 0.0
        print(f'[NOMINAL] nav={vs.nav_state if vs else None} p_spoof={prob:.3f} gps={fl.cs_gps if fl else None} of={fl.cs_opt_flow if fl else None} rng={fl.cs_rng_hgt if fl else None} hijack={err:.2f}m', flush=True)

print(f'\\n[DEMO] >>> INJECTING SPOOFING ATTACK: mode={MODE}, rate={RATE}, bearing={BEARING}, offset_n={OFFSET_N} <<<', flush=True)
aproc = subprocess.Popen([ADV_BIN, '--mode', MODE, '--rate-mps', RATE, '--bearing-deg', BEARING, '--offset-n', OFFSET_N, '--offset-e', OFFSET_E], preexec_fn=os.setsid)

t_end = time.monotonic() + DEMO_S
next_print = time.monotonic() + 0.5
while time.monotonic() < t_end:
    spin_for(0.05)
    if time.monotonic() >= next_print and st['lp'] and st['gt']:
        next_print += 1.0
        lp, gt, g, fl, vs = st['lp'], st['gt'], st['grd'], st['fl'], st['vs']
        gp = gt.pose.pose.position
        err = math.hypot(lp.x - gp.x, lp.y - gp.y)
        prob = g.get('spoof_prob') if g else 0.0
        fo = g.get('failover_active') if g else False
        print(f'[ACTIVE]  nav={vs.nav_state if vs else None} failover={fo} p_spoof={prob:.3f} gps={fl.cs_gps if fl else None} of={fl.cs_opt_flow if fl else None} rng={fl.cs_rng_hgt if fl else None} real_gz=({gp.y:.1f},{gp.x:.1f},{-gp.z:.1f}) hijack={err:.2f}m', flush=True)

kill_proc(aproc); kill_proc(mproc); kill_proc(gproc)
rclpy.shutdown()
print('[DEMO] Finished cleanly.', flush=True)
PY
"

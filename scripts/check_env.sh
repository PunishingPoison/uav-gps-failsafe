#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PASS=0
WARN=0
FAIL=0

ok()   { echo "[PASS] $*"; PASS=$((PASS + 1)); }
warn() { echo "[WARN] $*"; WARN=$((WARN + 1)); }
err()  { echo "[FAIL] $*"; FAIL=$((FAIL + 1)); }

echo "================================================================="
echo "  uav-gps-failsafe Environment Verification"
echo "================================================================="

# 1. Host OS & Memory
if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  echo "[INFO] Host OS: ${PRETTY_NAME:-unknown}"
fi
echo "[INFO] Host RAM: $(free -h | awk '/^Mem:/ {print $2 " total, " $7 " available"}')"

# 2. Display / GUI check
if [[ -n "${DISPLAY:-}" ]]; then
  ok "X11 DISPLAY is set (${DISPLAY})"
else
  warn "DISPLAY is unset; GUI Gazebo/QGC windows require X11 DISPLAY (headless mode still works)"
fi

# 3. QGroundControl check
if [[ -x /home/vcmr/Downloads/squashfs-root/AppRun ]] || [[ -x /home/vcmr/Downloads/QGroundControl.AppImage ]]; then
  ok "QGroundControl found on host"
else
  warn "QGroundControl binary not found in ~/Downloads"
fi

# 4. Docker & Base/Project Image check
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  ok "Docker daemon accessible ($(docker --version))"
else
  err "Docker CLI or daemon not accessible"
fi

TARGET_IMAGE=""
if docker image inspect uav-gps-failsafe:jazzy >/dev/null 2>&1; then
  TARGET_IMAGE="uav-gps-failsafe:jazzy"
  ok "Project Docker image uav-gps-failsafe:jazzy is present"
elif docker image inspect infynex-px4-sitl:jazzy >/dev/null 2>&1; then
  TARGET_IMAGE="infynex-px4-sitl:jazzy"
  warn "uav-gps-failsafe:jazzy not built yet; falling back to infynex-px4-sitl:jazzy"
else
  err "Neither uav-gps-failsafe:jazzy nor infynex-px4-sitl:jazzy Docker image found"
fi

# 5. Inside-container ROS 2 / PX4 / Gazebo / MicroXRCEAgent / Python check
if [[ -n "$TARGET_IMAGE" ]]; then
  echo "[INFO] Inspecting toolchain inside Docker image: $TARGET_IMAGE"
  docker run --rm --entrypoint bash "$TARGET_IMAGE" -c '
    set -e
    source /opt/ros/jazzy/setup.bash
    echo "  CONTAINER_OS=$(. /etc/os-release && echo "$PRETTY_NAME")"
    echo "  ROS_DISTRO=${ROS_DISTRO:-unknown}"
    echo "  GZ_VERSION=$(gz sim --version 2>/dev/null | head -n1 || echo missing)"
    echo "  UXRCE_AGENT=$(command -v MicroXRCEAgent || echo missing)"
    echo "  PX4_DIR=$(test -x /opt/PX4-Autopilot/build/px4_sitl_default/bin/px4 && echo /opt/PX4-Autopilot || echo missing)"
    echo "  PX4_TAG=$(git -C /opt/PX4-Autopilot describe --tags --always 2>/dev/null || echo unknown)"
    python3 - <<PY
import importlib
pkgs = ["rclpy", "pymavlink", "pyulog", "numpy", "matplotlib", "scipy", "cv2", "sklearn", "xgboost", "pandas", "joblib"]
missing = []
for p in pkgs:
    try:
        m = importlib.import_module(p)
        ver = getattr(m, "__version__", "installed")
        print(f"  PY_{p}={ver}")
    except Exception:
        missing.append(p)
if missing:
    print("  PY_MISSING=" + ",".join(missing))
    raise SystemExit(1)
PY
  ' && ok "Container toolchain verified" || err "Container toolchain check failed"
fi

# 6. px4_msgs ABI check
if [[ -d "${REPO_ROOT}/ros2_ws/src/px4_msgs/msg" ]]; then
  if [[ -f "${REPO_ROOT}/ros2_ws/src/px4_msgs/msg/SensorGps.msg" ]]; then
    ok "px4_msgs present with SensorGps.msg (PX4 v1.15 ABI)"
  else
    err "px4_msgs present but missing SensorGps.msg"
  fi
else
  err "ros2_ws/src/px4_msgs not found"
fi

# 7. gps_failsafe_pkg check
if [[ -f "${REPO_ROOT}/ros2_ws/src/gps_failsafe_pkg/package.xml" ]]; then
  ok "gps_failsafe_pkg skeleton present"
else
  err "gps_failsafe_pkg missing"
fi

echo "================================================================="
echo "Summary: PASS=${PASS} WARN=${WARN} FAIL=${FAIL}"
echo "================================================================="
[[ "$FAIL" -eq 0 ]]

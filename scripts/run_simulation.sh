#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONTAINER_NAME="uav_gps_failsafe_sim"
IMAGE_NAME="uav-gps-failsafe:jazzy"

HEADLESS=0
STOP_ONLY=0
DETACH=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --headless) HEADLESS=1; shift ;;
    --detach)   DETACH=1; shift ;;
    --stop)     STOP_ONLY=1; shift ;;
    -h|--help)
      echo "Usage: $0 [--headless] [--detach] [--stop]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

cleanup_container() {
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
}

if [[ "$STOP_ONLY" -eq 1 ]]; then
  cleanup_container
  echo "[SIM] Stopped container $CONTAINER_NAME."
  exit 0
fi

cleanup_container

DOCKER_FLAGS=(
  --name "$CONTAINER_NAME"
  --network host
  --ipc host
  --privileged
  -v "${REPO_ROOT}:/uav_ws"
  -v "${REPO_ROOT}/simulation/models/x500_flow_lidar:/opt/PX4-Autopilot/Tools/simulation/gz/models/x500_flow_lidar:ro"
  -v "${REPO_ROOT}/simulation/models/textured_ground:/opt/PX4-Autopilot/Tools/simulation/gz/models/textured_ground:ro"
  -v "${REPO_ROOT}/simulation/worlds/textured_field.sdf:/opt/PX4-Autopilot/Tools/simulation/gz/worlds/textured_field.sdf:ro"
  -v "${REPO_ROOT}/simulation/airframes/4015_gz_x500_flow_lidar:/opt/PX4-Autopilot/ROMFS/px4fmu_common/init.d-posix/airframes/4015_gz_x500_flow_lidar:ro"
  -v "${REPO_ROOT}/simulation/airframes/4015_gz_x500_flow_lidar:/opt/PX4-Autopilot/build/px4_sitl_default/etc/init.d-posix/airframes/4015_gz_x500_flow_lidar:ro"
)

if [[ -e /dev/dri ]]; then
  DOCKER_FLAGS+=(--device /dev/dri)
fi

if [[ "$HEADLESS" -eq 0 ]]; then
  export DISPLAY="${DISPLAY:-:0}"
  xhost +local:root >/dev/null 2>&1 || true
  xhost +local:docker >/dev/null 2>&1 || true
  DOCKER_FLAGS+=(
    -e "DISPLAY=${DISPLAY}"
    -e "QT_X11_NO_MITSHM=1"
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw
  )
  if [[ -e /dev/nvidia0 ]]; then
    DOCKER_FLAGS+=(
      -e NVIDIA_VISIBLE_DEVICES=all
      -e NVIDIA_DRIVER_CAPABILITIES=all
      --device /dev/nvidia0 --device /dev/nvidiactl --device /dev/nvidia-uvm
    )
    if [[ -e /usr/lib/x86_64-linux-gnu/libcuda.so.595.99.02 ]]; then
      DOCKER_FLAGS+=(
        -v /usr/lib/x86_64-linux-gnu/libcuda.so.595.99.02:/usr/lib/x86_64-linux-gnu/libcuda.so.1:ro
        -v /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.595.99.02:/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1:ro
      )
    fi
  fi
fi

if [[ "$DETACH" -eq 1 ]]; then
  DOCKER_FLAGS+=(-d)
else
  DOCKER_FLAGS+=(--rm -i)
fi

CMD_SCRIPT=$(cat <<EOF
set -e
source /opt/ros/jazzy/setup.bash
source /uav_ws/ros2_ws/install/setup.bash

mkdir -p /tmp/uav_logs /tmp/runtime-root
chmod 700 /tmp/runtime-root
export XDG_RUNTIME_DIR=/tmp/runtime-root
export GZ_SIM_RESOURCE_PATH="/uav_ws/simulation/models:/uav_ws/simulation/worlds:/opt/PX4-Autopilot/Tools/simulation/gz/models:/opt/PX4-Autopilot/Tools/simulation/gz/worlds"

GZ_RENDER_FLAGS="-s -r"
if [[ "${HEADLESS}" -eq 1 ]]; then
  # Headless rendering is required for Gazebo camera + gpu_lidar without a GUI window
  if [[ ! -e /dev/dri ]]; then
    export EGL_PLATFORM=surfaceless
    export LIBGL_ALWAYS_SOFTWARE="\${LIBGL_ALWAYS_SOFTWARE:-1}"
  fi
  GZ_RENDER_FLAGS="-s -r --headless-rendering"
fi

echo "[SIM] Starting Gazebo Harmonic (world=textured_field, headless=${HEADLESS})..."
gz sim \${GZ_RENDER_FLAGS} /uav_ws/simulation/worlds/textured_field.sdf > /tmp/uav_logs/gz_server.log 2>&1 &
GZ_SRV_PID=\$!

for i in \$(seq 1 30); do
  if gz service -l 2>/dev/null | grep -q "/world/textured_field/create"; then
    echo "[SIM] Gazebo world /world/textured_field ready (\${i}s)"
    break
  fi
  sleep 1
done

if [[ "${HEADLESS}" -eq 0 ]]; then
  gz sim -g > /tmp/uav_logs/gz_gui.log 2>&1 &
  GZ_GUI_PID=\$!
fi

echo "[SIM] Starting MicroXRCEAgent on UDP:8888..."
MicroXRCEAgent udp4 -p 8888 > /tmp/uav_logs/uxrce.log 2>&1 &
XRCE_PID=\$!

echo "[SIM] Starting PX4 SITL (x500_flow_lidar, autostart=4015)..."
cd /opt/PX4-Autopilot/build/px4_sitl_default
rm -f parameters.bson*
export PX4_SYS_AUTOSTART=4015
export PX4_SIM_MODEL=gz_x500_flow_lidar
export PX4_GZ_STANDALONE=1
export PX4_GZ_WORLD=textured_field
export PX4_GZ_MODEL_POSE="0,0,0.25,0,0,0"
./bin/px4 -d etc -s etc/init.d-posix/rcS > /tmp/uav_logs/px4.log 2>&1 &
PX4_PID=\$!

for i in \$(seq 1 30); do
  if gz topic -l 2>/dev/null | grep -q "/gz/downward_lidar/scan"; then
    echo "[SIM] Model x500_flow_lidar_0 spawned and sensor topics active (\${i}s)"
    break
  fi
  sleep 1
done

echo "[SIM] Starting ros_gz_bridge for camera, 1D LiDAR, NavSat, and ground-truth odom..."
ros2 run ros_gz_bridge parameter_bridge \
  /gz/downward_camera/image@sensor_msgs/msg/Image[gz.msgs.Image \
  /gz/downward_lidar/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan \
  /world/textured_field/model/x500_flow_lidar_0/link/base_link/sensor/navsat_sensor/navsat@sensor_msgs/msg/NavSatFix[gz.msgs.NavSat \
  /gz/ground_truth/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry \
  --ros-args \
  -r /world/textured_field/model/x500_flow_lidar_0/link/base_link/sensor/navsat_sensor/navsat:=/gz/navsat \
  > /tmp/uav_logs/ros_gz_bridge.log 2>&1 &
BRIDGE_PID=\$!

echo "[SIM] Starting gps_failsafe_pkg sensor_bridge_node..."
ros2 run gps_failsafe_pkg sensor_bridge_node > /tmp/uav_logs/sensor_bridge.log 2>&1 &
SB_PID=\$!

trap 'kill \$SB_PID \$BRIDGE_PID \$PX4_PID \$XRCE_PID \$GZ_SRV_PID \${GZ_GUI_PID:-} 2>/dev/null || true' EXIT INT TERM
echo "[SIM] All simulation components running. Logs in /tmp/uav_logs/"
wait \$PX4_PID
EOF
)

if [[ "$DETACH" -eq 1 ]]; then
  docker run "${DOCKER_FLAGS[@]}" "$IMAGE_NAME" bash -c "$CMD_SCRIPT"
  echo "[SIM] Detached container $CONTAINER_NAME started."
  echo "[SIM] Inspect logs with: docker exec $CONTAINER_NAME tail -f /tmp/uav_logs/px4.log /tmp/uav_logs/sensor_bridge.log"
else
  docker run "${DOCKER_FLAGS[@]}" "$IMAGE_NAME" bash -c "$CMD_SCRIPT"
fi

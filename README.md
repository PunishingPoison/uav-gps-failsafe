# Simulated Failsafe Architectures for GPS-Denied Drone Navigation and Cyber-Attack Recovery

Reproducible PX4 Autopilot SITL + Gazebo Harmonic + ROS 2 + Machine Learning testbed that detects real-time GPS spoofing attacks (Step, Slow Drift/Meaconing, and Coordinated Takeover) and executes automated failover to GPS-denied navigation using downward Optical Flow and 1D LiDAR rangefinding.

## Architecture Overview

- **Autopilot & Simulator:** PX4 Autopilot `v1.15.4` SITL + Gazebo Harmonic (`8.15.0`) + QGroundControl
- **Middleware:** ROS 2 Jazzy + Micro XRCE-DDS Agent (`v2.4.3`) + `px4_msgs` (`release/1.15`)
- **Runtime Container:** `uav-gps-failsafe:jazzy` (layered on `infynex-px4-sitl:jazzy` so PX4 `v1.15.4` is pre-compiled and isolated from host OS Python/ROS differences)
- **Sensors:** GNSS (`HIL_GPS` / simulated GPS), downward camera Optical Flow (`/fmu/in/sensor_optical_flow`), downward 1D LiDAR (`DISTANCE_SENSOR`), IMU + Barometer

## Repository Structure

```text
uav-gps-failsafe/
├── docker/                            # Project container image layered over infynex-px4-sitl:jazzy
├── scripts/                           # Environment checks, sim launcher (--headless / GUI), EKF2 parameter setup, demo runner
├── simulation/                        # Custom textured Gazebo worlds, multi-sensor x500 SDF models, PX4 airframe config
├── ros2_ws/src/
│   ├── px4_msgs/                      # PX4 ROS 2 message definitions pinned to release/1.15
│   └── gps_failsafe_pkg/              # Mission runner, sensor bridge, adversary spoofer, logger, feature extractor, AI guardian
├── ml/                                # Training & evaluation scripts + saved .joblib models
├── analysis/                          # Experiment evaluation (latency, RMSE, drift) and paper figure plotting
└── data/                              # Raw & processed flight telemetry datasets
```

## Quick Verification (Phase 1)

```bash
./scripts/check_env.sh
```

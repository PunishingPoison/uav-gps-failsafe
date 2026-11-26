# Simulated Failsafe Architectures for GPS-Denied Drone Navigation and Cyber-Attack Recovery

Reproducible PX4 Autopilot SITL + Gazebo Harmonic + ROS 2 + Machine Learning testbed that detects real-time GPS spoofing attacks (Step, Slow Drift/Meaconing, and Coordinated Takeover) and executes automated failover to GPS-denied navigation using downward Optical Flow and 1D LiDAR rangefinding.

## Architecture Overview

- **Autopilot & Simulator:** PX4 Autopilot `v1.15.4` SITL + Gazebo Harmonic (`8.15.0`) + QGroundControl
- **Middleware:** ROS 2 Jazzy + Micro XRCE-DDS Agent (`v2.4.3`) + `px4_msgs` (`release/1.15`)
- **Runtime Container:** `uav-gps-failsafe:jazzy` (layered on `infynex-px4-sitl:jazzy` so PX4 `v1.15.4` is pre-compiled and isolated from host OS Python/ROS differences)
- **Sensors:** GNSS (`HIL_GPS` on `14030`/`13030`), downward camera Optical Flow (`OPTICAL_FLOW_RAD` via OpenCV Lucas-Kanade), downward 1D LiDAR (`DISTANCE_SENSOR`), IMU + Barometer

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

## Quick Verification & Usage (Phases 1–3)

1. **Verify container, ROS 2, PX4, Gazebo, and Python stack (Phase 1):**
```bash
./scripts/check_env.sh
```

2. **Launch simulation + sensor bridge + MicroXRCEAgent (Phase 2):**
```bash
./scripts/run_simulation.sh --headless --detach
docker exec uav_gps_failsafe_sim python3 /uav_ws/scripts/configure_ekf2_params.py --mode status
```

3. **Run autonomous mission & GPS spoofing adversary inside container (Phase 3):**
```bash
docker exec -it uav_gps_failsafe_sim bash -c '
  source /opt/ros/jazzy/setup.bash && source /uav_ws/ros2_ws/install/setup.bash
  ros2 run gps_failsafe_pkg mission_runner_node --pattern square --size 12.0 --altitude 4.0 --loops 2
'
```
In a second terminal (while mission runs), launch one of the three attack profiles (`step`, `drift`, or `takeover`):
```bash
docker exec -it uav_gps_failsafe_sim bash -c '
  source /opt/ros/jazzy/setup.bash && source /uav_ws/ros2_ws/install/setup.bash
  ros2 run gps_failsafe_pkg adversary_spoofer_node --mode drift --rate-mps 2.0 --bearing-deg 0.0
'
```
Switch EKF2 parameters manually (nominal vs GPS-denied failover) or stop simulation cleanly:
```bash
docker exec uav_gps_failsafe_sim python3 /uav_ws/scripts/configure_ekf2_params.py --mode gps-denied
./scripts/run_simulation.sh --stop
```

4. **Generate multi-episode dataset & train/evaluate AI detectors (Phase 4):**
```bash
python3 ml/collect_dataset.py
docker run --rm -v "$PWD:/uav_ws" uav-gps-failsafe:jazzy bash -c '
  python3 /uav_ws/ml/train_models.py && python3 /uav_ws/ml/evaluate_models.py
'
```

5. **Run live AI Guardian with automated failover (Phase 5):**
```bash
./scripts/run_simulation.sh --detach
docker exec -it uav_gps_failsafe_sim bash -c '
  source /opt/ros/jazzy/setup.bash && source /uav_ws/ros2_ws/install/setup.bash
  ros2 run gps_failsafe_pkg guardian_ai_node --model rf --threshold 0.80 --consecutive 5
'
```
While running `mission_runner_node` + `adversary_spoofer_node` in parallel terminals, the Guardian cuts `EKF2_GPS_CTRL=0`, sets `EKF2_HGT_REF=2`, and engages `AUTO.LOITER` GPS-denied hover automatically.

## Roadmap Progress

- [x] **Phase 1:** Dockerized PX4 SITL (`v1.15.4`), Gazebo Harmonic, ROS 2 Jazzy, `px4_msgs`, and workspace setup
- [x] **Phase 2:** Textured Gazebo field, custom `x500_flow_lidar` model + airframe `4015`, `sensor_bridge_node`, EKF2 failover verified
- [x] **Phase 3:** `mission_runner_node` + `adversary_spoofer_node` (`step`, `drift`, `takeover`) verified visually in Gazebo GUI (`fused: True`)
- [x] **Phase 4:** `telemetry_logger_node`, 24-feature sliding-window `feature_extractor`, 16-episode dataset, RF (`F1=0.9426`, `AUC=0.9879`) & XGBoost (`F1=0.9369`, `AUC=0.9885`) trained and evaluated
- [x] **Phase 5:** Real-time `guardian_ai_node` automated MAVLink failover (`EKF2_GPS_CTRL=0`, `AUTO.LOITER`) verified with zero nominal false triggers across `step`, `drift`, and `takeover`
- [ ] **Phase 6:** Automated ablation experiments & publication-grade paper figures

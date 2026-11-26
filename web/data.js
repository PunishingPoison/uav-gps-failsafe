// Structured single-source data store for the UAV GPS-Failsafe technical portal.
// Update this file alongside project enhancements to keep every tab synchronized.

export const PROJECT_META = {
  title: "Simulated Failsafe Architectures for GPS-Denied UAV Navigation and Cyber-Attack Recovery",
  shortTitle: "UAV GPS-Failsafe",
  subtitle:
    "An autonomous PX4 SITL, Gazebo Harmonic, ROS 2, and Machine Learning architecture that detects GNSS spoofing in real time and executes sub-10 ms failover to downward Optical Flow and 1D LiDAR navigation.",
  repoUrl: "https://github.com/PunishingPoison/uav-gps-failsafe",
  academic: {
    institution: "B.M.S. College of Engineering (Autonomous Institute, Affiliated to VTU, Belagavi)",
    department: "Department of Machine Learning (B.E. in Artificial Intelligence and Machine Learning)",
    course: "Mini Project Work",
    courseCode: "24AM5PWMPW",
    reviewStage: "Review - 1",
    reviewDate: "28-11-2026",
    academicYear: "2026-27",
    semesterSection: "5 '_'",
    teamNumber: "[Team Number]",
    students: ["<student 1 name & usn>", "<student 2 name & usn>", "<student 3 name & usn>"],
    facultyInCharge: "Dr. / Prof. [Type faculty name here] (Assistant / Associate / Professor, Dept. of ML)",
  },
  headlineMetrics: [
    { label: "Random Forest Test F1", value: "0.9426", detail: "ROC-AUC 0.9879 on unseen flights", tone: "cobalt" },
    { label: "XGBoost Test ROC-AUC", value: "0.9885", detail: "Test F1 0.9369, Precision 0.9599", tone: "cobalt" },
    { label: "AI Guardian Cutover", value: "6.7–8.2 ms", detail: "MAVLink EKF2_GPS_CTRL=0 + HOLD", tone: "emerald" },
    { label: "Hijack Excursion Cut", value: "21.26 m → 0.19 m", detail: "Under 2.2 m/s coordinated takeover", tone: "carmine" },
  ],
};

export const PROBLEM_AND_SCOPE = {
  introduction:
    "Small uncrewed aerial vehicles (UAVs) performing urban inspection, surveying, or corridor patrol depend heavily on unencrypted civilian GNSS signals (L1 C/A GPS). In urban canyons and adversarial airspace, multipath attenuation or intentional RF spoofing can silently corrupt GNSS measurements. Once PX4's Extended Kalman Filter (EKF2) fuses falsified latitude/longitude fixes, closed-loop position control steers the physical airframe along an attacker-dictated trajectory even though the onboard HUD appears nominal.",
  problemStatement:
    "Civilian multirotor autopilots lack onboard cross-sensor AI supervision capable of distinguishing gradual meaconing drifts and smooth coordinated takeovers from sharp flight maneuvers, and lack automated parameter cutover to self-contained Optical Flow + 1D LiDAR localization before dangerous spatial divergence occurs.",
  objectives: [
    {
      id: "Objective 1",
      title: "Build a Reproducible Cyber-Physical UAV Digital Twin",
      description:
        "Configure a containerized PX4 v1.15.4 SITL + Gazebo Harmonic (gz-sim8) + ROS 2 Jazzy testbed equipped with a downward Optical Flow camera (128x128 @ 30 Hz), 1D LiDAR (0.05–60 m @ 30 Hz), and preemptible HIL_GPS receiver supporting Step, Drift, and Coordinated Takeover spoofing profiles.",
    },
    {
      id: "Objective 2",
      title: "Train Leakage-Free Cross-Sensor AI Spoofing Detectors",
      description:
        "Collect multi-episode synchronized telemetry across nominal and spoofed flights, engineer a strictly causal 24-feature sliding-window extractor combining EKF2 residuals, GPS drift index, IMU velocity changes, and Optical Flow cross-checks, and benchmark Random Forest and XGBoost classifiers on unseen test episodes.",
    },
    {
      id: "Objective 3",
      title: "Execute Real-Time Automated GPS-Denied Failover",
      description:
        "Deploy guardian_ai_node at 20 Hz with sustained multi-tick gating (p >= 0.80 for 5 ticks) to disable GPS fusion (EKF2_GPS_CTRL=0), promote Optical Flow + LiDAR (EKF2_HGT_REF=2, EKF2_OF_CTRL=1, EKF2_RNG_CTRL=2), and lock safe hover (AUTO.LOITER) with zero nominal false triggers.",
    },
  ],
  scopeBounds: [
    "Software-in-the-loop (SITL) aerodynamic, IMU, magnetometer, downward optical flow (Lucas-Kanade), 1D rangefinder, and HIL_GPS simulation on textured ground environments.",
    "Three adversarial GNSS threat profiles calibrated against EKF2 innovation gates: sudden step jumps, linear drift/meaconing ramps, and S-curve smooth coordinated takeovers.",
    "Post-detection failsafe state hold (AUTO.LOITER + GPS isolation) paired with binary PX4 .ulg flight log and 20 Hz ROS 2 CSV validation across 10 paired experiments.",
    "Out of scope: physical SDR RF hardware-in-the-loop transmission, raw I/Q carrier-phase signal processing, and multi-agent swarm consensus.",
  ],
};

export const PROJECT_FLOW = [
  {
    step: "01",
    title: "Digital Twin & Multi-Sensor Bridge",
    detail:
      "Dockerized PX4 SITL v1.15.4 (airframe 4015) flies the custom x500_flow_lidar quadrotor over a textured_field world. sensor_bridge_node fuses Gazebo 128x128 downward camera via OpenCV Lucas-Kanade optical flow (OPTICAL_FLOW_RAD) and 1D LiDAR (DISTANCE_SENSOR) at 30 Hz alongside nominal HIL_GPS (10 Hz).",
    artifacts: "simulation/airframes/4015_gz_x500_flow_lidar, sensor_bridge_node.py",
  },
  {
    step: "02",
    title: "Autonomous Path & Spoof Injection",
    detail:
      "mission_runner_node executes repeatable NED waypoint flights (12x12 m square: WP1 Top-Left -> WP2 Top-Right -> WP3 Bottom-Right -> WP4 Bottom-Left). adversary_spoofer_node preempts HIL_GPS on UDP 13030 with Step, Drift, or S-curve Takeover offsets from the Rogue TX (-8, +8).",
    artifacts: "mission_runner_node.py, adversary_spoofer_node.py",
  },
  {
    step: "03",
    title: "16-Episode Telemetry Logging",
    detail:
      "telemetry_logger_node records 20 Hz synchronized observables (74 raw columns across PX4 uXRCE-DDS topics and Optical Flow) across 16 standalone episodes (4 Nominal, 4 Step, 4 Drift, 4 Takeover), split strictly by episode (12 train / 4 held-out test).",
    artifacts: "telemetry_logger_node.py, ml/collect_dataset.py, data/raw/*.csv",
  },
  {
    step: "04",
    title: "Causal 24-Feature Engineering",
    detail:
      "FeatureWindowExtractor processes a 20-sample (1.0 s) causal window strictly from onboard telemetry (zero ground-truth or adversary leakage), computing 24 features spanning EKF2 residuals, GDI, GPS kinematics, IMU integration, and gyro-compensated Optical Flow cross-checks.",
    artifacts: "feature_extractor.py, data/processed/features_dataset.csv",
  },
  {
    step: "05",
    title: "Model Training & Calibration",
    detail:
      "ml/train_models.py runs 4-fold StratifiedGroupKFold cross-validation grouped by episode to prevent sliding-window leakage, comparing a tuned Threshold Baseline against Random Forest (250 trees) and XGBoost (250 boosted trees, depth 4).",
    artifacts: "ml/train_models.py, ml/evaluate_models.py, ml/models/*.joblib",
  },
  {
    step: "06",
    title: "Real-Time Guardian Failover & Ablation",
    detail:
      "guardian_ai_node scores live 20 Hz windows, triggers atomic MAVLink PARAM_SET failover (EKF2_GPS_CTRL=0, EKF2_HGT_REF=2) + AUTO.LOITER in 6.7–8.2 ms, and is verified across 10 paired ULog/CSV experiments and a sequential OFF-then-ON GUI demo.",
    artifacts: "guardian_ai_node.py, demo_hud_node.py, scripts/run_demo.sh, analysis/*.py",
  },
];

export const FEATURE_GROUPS = [
  {
    group: "1. GPS-vs-EKF2 Position Residuals & Drift Index (7 features)",
    rationale: "Measures instantaneous horizontal separation and linear growth trend between projected WGS84 GPS coordinates and fused EKF2 local NED position.",
    features: [
      { name: "pos_res_xy_curr", desc: "Instantaneous 2D horizontal distance ||p_gps,xy - p_est,xy|| [m]." },
      { name: "pos_res_xy_mean", desc: "Window mean of horizontal position residual [m] (XGBoost #1 feature)." },
      { name: "pos_res_xy_max", desc: "Peak horizontal position residual inside 1.0 s window [m] (RF #1 feature)." },
      { name: "pos_res_xy_std", desc: "Standard deviation of position residual capturing jump vs steady tracking [m]." },
      { name: "pos_res_xy_slope", desc: "Linear least-squares slope of position residual over window [m/sample]." },
      { name: "gdi_net_xy", desc: "GPS Drift Index: cumulative net vector displacement of (GPS - Est) across window [m]." },
      { name: "gdi_rate_mps", desc: "Time-normalized GDI drift magnitude over window duration [m/s]." },
    ],
  },
  {
    group: "2. GPS-vs-EKF2 Velocity Divergence (4 features)",
    rationale: "Captures velocity biases introduced during smooth drift/meaconing and coordinated velocity ramp attacks before large position offset accumulates.",
    features: [
      { name: "vel_res_xy_curr", desc: "Current horizontal velocity residual ||v_gps,xy - v_est,xy|| [m/s]." },
      { name: "vel_res_xy_mean", desc: "Window mean of GPS vs EKF2 horizontal velocity residual [m/s]." },
      { name: "vel_res_xy_max", desc: "Maximum velocity residual across window [m/s]." },
      { name: "vel_res_xy_std", desc: "Spread of velocity residual across the 20-sample buffer [m/s]." },
    ],
  },
  {
    group: "3. GPS Internal Kinematics & Optical-Flow Displacement Check (5 features)",
    rationale: "Detects step discontinuities in raw GPS independent of filter state and compares GPS path length against Optical Flow dead-reckoned motion.",
    features: [
      { name: "gps_jump_xy_curr", desc: "Instantaneous frame-to-frame raw GPS position jump minus integrated GPS velocity [m]." },
      { name: "gps_jump_xy_max", desc: "Peak raw GPS step jump within the sliding window [m] (XGBoost #3 feature)." },
      { name: "gps_kin_win_err", desc: "Window integral discrepancy ||Delta p_gps - integral(v_gps dt)|| [m]." },
      { name: "gps_kin_win_rate", desc: "Rate-normalized kinematic mismatch between GPS position and velocity [m/s]." },
      { name: "of_gps_disp_err", desc: "Mismatch between Optical-Flow-integrated displacement and GPS displacement [m]." },
    ],
  },
  {
    group: "4. IMU Specific Force vs Velocity Change Divergence (3 features)",
    rationale: "Gravity-compensated body-to-NED rotated accelerometer integral provides a physics-invariant motion baseline that RF spoofing cannot manipulate.",
    features: [
      { name: "imu_gps_dv_err", desc: "||Delta v_gps - integral(a_ned dt)|| over the 1.0 s window [m/s]." },
      { name: "imu_gps_acc_half_err", desc: "Acceleration difference magnitude over half-window sub-interval." },
      { name: "imu_est_dv_err", desc: "||Delta v_est - integral(a_ned dt)|| checking internal EKF2 consistency [m/s]." },
    ],
  },
  {
    group: "5. Downward Optical Flow + 1D LiDAR Cross-Check (5 features)",
    rationale: "Transforms gyro-compensated optical angular rates scaled by downward 1D LiDAR range into NED ground velocity (empirically R > 0.99, RMSE 0.24 m/s).",
    features: [
      { name: "of_gps_vel_diff_curr", desc: "Current ||v_flow,xy - v_gps,xy|| discrepancy magnitude [m/s]." },
      { name: "of_gps_vel_diff_mean", desc: "Window mean velocity divergence between Optical Flow and GPS [m/s]." },
      { name: "of_gps_vel_diff_max", desc: "Peak Optical Flow vs GPS velocity mismatch in window [m/s]." },
      { name: "of_speed_ratio_err_mean", desc: "Mean normalized scalar speed mismatch |s_flow - s_gps| / max(1, s_flow)." },
      { name: "of_est_vel_diff_mean", desc: "Mean divergence between Optical Flow and EKF2 estimate [m/s]." },
    ],
  },
];

export const DATASET_SUMMARY = {
  rawRateHz: 20,
  windowSize: 20,
  minSamples: 10,
  totalEpisodes: 16,
  trainEpisodesCount: 12,
  testEpisodesCount: 4,
  totalFeatureWindows: 7621,
  trainRows: 5694,
  testRows: 1927,
  rawColumnsCount: 74,
  featureColumnsCount: 24,
  leakagePolicy: "Episode-level strict separation + airborne_only=True; zero gt_* or spoof_* columns read during feature extraction.",
};

export const DATASET_EPISODES = [
  { id: "ep_nom_01_hover", split: "train", mode: "none", pattern: "hover", speed: "1.5 m/s", params: "No spoofing (baseline)", lines: 572 },
  { id: "ep_nom_02_square_norm", split: "train", mode: "none", pattern: "square (12 m)", speed: "2.0 m/s", params: "90 deg turns", lines: 611 },
  { id: "ep_nom_03_line_rev", split: "train", mode: "none", pattern: "line (12 m)", speed: "2.5 m/s", params: "180 deg reversals", lines: 617 },
  { id: "ep_nom_04_square_fast", split: "test", mode: "none", pattern: "square (14 m)", speed: "2.8 m/s", params: "Held-out aggressive nominal", lines: 608 },
  { id: "ep_step_01_4m_n", split: "train", mode: "step", pattern: "hover", speed: "2.0 m/s", params: "offset_n=+4.0 m", lines: 552 },
  { id: "ep_step_02_3p5m_diag", split: "train", mode: "step", pattern: "square (12 m)", speed: "2.0 m/s", params: "offset=(+2.6, -2.6) m", lines: 553 },
  { id: "ep_step_03_12m_spike", split: "train", mode: "step", pattern: "line (12 m)", speed: "2.0 m/s", params: "offset_n=+12.0 m spike", lines: 618 },
  { id: "ep_step_04_3p8m_e", split: "test", mode: "step", pattern: "square (12 m)", speed: "2.2 m/s", params: "Held-out offset_e=+3.8 m", lines: 551 },
  { id: "ep_drift_01_0p8mps", split: "train", mode: "drift", pattern: "square (12 m)", speed: "2.0 m/s", params: "rate=0.8 m/s @ 0 deg", lines: 572 },
  { id: "ep_drift_02_1p8mps_sw", split: "train", mode: "drift", pattern: "line (12 m)", speed: "2.2 m/s", params: "rate=1.8 m/s @ 225 deg", lines: 552 },
  { id: "ep_drift_03_2p5mps_e", split: "train", mode: "drift", pattern: "hover", speed: "2.0 m/s", params: "rate=2.5 m/s @ 90 deg", lines: 538 },
  { id: "ep_drift_04_1p2mps_nw", split: "test", mode: "drift", pattern: "square (12 m)", speed: "2.2 m/s", params: "Held-out rate=1.2 m/s @ 315 deg", lines: 578 },
  { id: "ep_take_01_1p2mps", split: "train", mode: "takeover", pattern: "hover", speed: "2.0 m/s", params: "rate=1.2 m/s @ 45 deg, ramp=3.0 s", lines: 571 },
  { id: "ep_take_02_2p5mps", split: "train", mode: "takeover", pattern: "square (12 m)", speed: "2.0 m/s", params: "rate=2.5 m/s @ 180 deg, ramp=2.0 s", lines: 554 },
  { id: "ep_take_03_3p0mps_ne", split: "train", mode: "takeover", pattern: "line (12 m)", speed: "2.2 m/s", params: "rate=3.0 m/s @ 225 deg, ramp=1.8 s", lines: 540 },
  { id: "ep_take_04_1p6mps_se", split: "test", mode: "takeover", pattern: "square (12 m)", speed: "2.2 m/s", params: "Held-out 1.6 m/s @ 135 deg", lines: 571 },
];

export const MODEL_EVALUATION = {
  models: [
    {
      name: "Threshold Baseline",
      role: "Heuristic Reference (pos_res > 0.7 m or vel_res > 0.5 m/s)",
      threshold: "0.70 m / 0.50 m/s",
      accuracy: "0.9294",
      precision: "0.9842",
      recall: "0.8461",
      f1: "0.9099",
      rocAuc: "0.9663",
      prAuc: "0.9692",
      nominalFpr: "0.0099",
      stepRecall: "0.6850",
      driftRecall: "0.9892",
      takeoverRecall: "0.8500",
      latStep: "0.2 s",
      latDrift: "0.2 s",
      latTakeover: "0.3 s",
      cvNote: "Grid-searched on training episodes for FPR <= 2%.",
    },
    {
      name: "Random Forest (Default Live)",
      role: "250 trees, max_depth=12, min_samples_leaf=3, class_weight='balanced'",
      threshold: "0.64 (CV) / 0.80 (Online Gate)",
      accuracy: "0.9523",
      precision: "0.9557",
      recall: "0.9298",
      f1: "0.9426",
      rocAuc: "0.9879",
      prAuc: "0.9872",
      nominalFpr: "0.0314",
      stepRecall: "0.8583",
      driftRecall: "0.9856",
      takeoverRecall: "0.9393",
      latStep: "0.2 s",
      latDrift: "0.3 s",
      latTakeover: "0.4 s",
      cvNote: "4-Fold StratifiedGroupKFold OOF: F1=0.9657, AUC=0.9772, FPR=0.0009.",
    },
    {
      name: "XGBoost Classifier",
      role: "250 trees, max_depth=4, lr=0.05, min_child_weight=5, reg_lambda=2.0, subsample=0.85",
      threshold: "0.82",
      accuracy: "0.9481",
      precision: "0.9599",
      recall: "0.9150",
      f1: "0.9369",
      rocAuc: "0.9885",
      prAuc: "0.9858",
      nominalFpr: "0.0278",
      stepRecall: "0.8583",
      driftRecall: "0.9784",
      takeoverRecall: "0.9036",
      latStep: "0.3 s",
      latDrift: "0.4 s",
      latTakeover: "0.5 s",
      cvNote: "4-Fold StratifiedGroupKFold OOF: F1=0.9515, AUC=0.9797, FPR=0.0024.",
    },
  ],
};

export const ABLATION_RUNS = [
  { runId: "exp_nominal_guarded", mode: "Nominal (Fast 2.5 m/s)", guardian: true, preRmse: "0.282 m", falseFailover: "False", latencyMs: "—", hijackRmse: "0.282 m", maxErr: "0.481 m", hoverDrift: "—", tailGpsPct: "85.7%", cutover: "Nominal" },
  { runId: "exp_step_unguarded", mode: "Step (+4.0 m N)", guardian: false, preRmse: "0.288 m", falseFailover: "False", latencyMs: "—", hijackRmse: "2.672 m", maxErr: "3.595 m", hoverDrift: "—", tailGpsPct: "85.7%", cutover: "No" },
  { runId: "exp_step_guarded", mode: "Step (+4.0 m N)", guardian: true, preRmse: "0.264 m", falseFailover: "False", latencyMs: "600 ms", hijackRmse: "0.210 m", maxErr: "0.275 m", hoverDrift: "0.0027 m/s", tailGpsPct: "0.0%", cutover: "Verified (.ulg)" },
  { runId: "exp_drift_0p8_unguarded", mode: "Slow Drift (0.8 m/s)", guardian: false, preRmse: "0.315 m", falseFailover: "False", latencyMs: "—", hijackRmse: "3.982 m", maxErr: "7.539 m", hoverDrift: "—", tailGpsPct: "85.7%", cutover: "No" },
  { runId: "exp_drift_0p8_guarded", mode: "Slow Drift (0.8 m/s)", guardian: true, preRmse: "0.269 m", falseFailover: "False", latencyMs: "549 ms", hijackRmse: "0.194 m", maxErr: "0.222 m", hoverDrift: "0.0140 m/s", tailGpsPct: "0.0%", cutover: "Verified (.ulg)" },
  { runId: "exp_drift_1p5_guarded", mode: "Mid Drift (1.5 m/s)", guardian: true, preRmse: "0.223 m", falseFailover: "False", latencyMs: "400 ms", hijackRmse: "0.194 m", maxErr: "0.242 m", hoverDrift: "0.0007 m/s", tailGpsPct: "0.0%", cutover: "Verified (.ulg)" },
  { runId: "exp_drift_2p2_unguarded", mode: "Fast Drift (2.2 m/s)", guardian: false, preRmse: "0.229 m", falseFailover: "False", latencyMs: "—", hijackRmse: "10.799 m", maxErr: "20.020 m", hoverDrift: "—", tailGpsPct: "85.7%", cutover: "No" },
  { runId: "exp_drift_2p2_guarded", mode: "Fast Drift (2.2 m/s)", guardian: true, preRmse: "0.255 m", falseFailover: "False", latencyMs: "300 ms", hijackRmse: "0.507 m", maxErr: "0.641 m", hoverDrift: "0.0059 m/s", tailGpsPct: "0.0%", cutover: "Verified (.ulg)" },
  { runId: "exp_takeover_unguarded", mode: "Takeover (2.2 m/s)", guardian: false, preRmse: "0.188 m", falseFailover: "False", latencyMs: "—", hijackRmse: "11.606 m", maxErr: "21.258 m", hoverDrift: "—", tailGpsPct: "85.7%", cutover: "No" },
  { runId: "exp_takeover_guarded", mode: "Takeover (2.2 m/s)", guardian: true, preRmse: "0.282 m", falseFailover: "False", latencyMs: "500 ms", hijackRmse: "0.176 m", maxErr: "0.188 m", hoverDrift: "0.0041 m/s", tailGpsPct: "0.0%", cutover: "Verified (.ulg)" },
];

export const CODE_MODULES = [
  {
    layer: "ROS 2 Online Nodes (ros2_ws/src/gps_failsafe_pkg/)",
    files: [
      { path: "sensor_bridge_node.py", role: "Gazebo->PX4 bridge: 30 Hz Lucas-Kanade OPTICAL_FLOW_RAD, 30 Hz 1D LiDAR DISTANCE_SENSOR, and preemptible 10 Hz HIL_GPS (UDP 14030)." },
      { path: "mission_runner_node.py", role: "Offboard flight controller executing repeatable NED square (WP1..WP4 -> Center), line, and hover paths; yields on /guardian/failover_active." },
      { path: "adversary_spoofer_node.py", role: "Threat injector asserting /adversary/active and pushing biased HIL_GPS packets (step, drift, takeover) to PX4 UDP 13030." },
      { path: "feature_extractor.py", role: "Shared online/offline sliding-window FeatureWindowExtractor computing the exact 24 causal telemetry features without ground-truth leakage." },
      { path: "guardian_ai_node.py", role: "20 Hz ML supervisor (RF/XGBoost). Sustained 5-tick threshold triggers atomic MAVLink PARAM_SET failover and AUTO.LOITER command." },
      { path: "ekf2_param_client.py", role: "MAVLink parameter helper implementing C-union struct INT32 bit-reinterpretation so PX4 accepts integer EKF2 flags cleanly." },
      { path: "telemetry_logger_node.py", role: "20 Hz synchronized CSV recorder joining PX4 estimator/GPS/IMU topics, optical flow, and experimental labels." },
      { path: "demo_hud_node.py", role: "Gazebo 3D MarkerManager overlay publisher (/marker_array) + 820x820 real-time Tactical Cyber-Attack & AI Guardian HUD." },
    ],
  },
  {
    layer: "Machine Learning & Evaluation (ml/)",
    files: [
      { path: "ml/collect_dataset.py", role: "Automated multi-episode SITL harness generating 16 standalone raw telemetry logs into data/raw/ with dataset_manifest.json." },
      { path: "ml/train_models.py", role: "4-fold StratifiedGroupKFold episode-grouped CV, threshold calibration, and persistence of RF, XGBoost, and Baseline .joblib models." },
      { path: "ml/evaluate_models.py", role: "Computes unseen-episode classification metrics, per-attack recall, detection latency, confusion matrices, and ROC/PR curves." },
      { path: "ml/baseline_detector.py", role: "Deterministic residual-threshold baseline wrapper providing identical scikit-learn predict/predict_proba interfaces." },
    ],
  },
  {
    layer: "Simulation, Infrastructure & Ablation (simulation/, scripts/, analysis/)",
    files: [
      { path: "simulation/models/x500_flow_lidar/model.sdf", role: "Quadrotor SDF adding OdometryPublisher (50 Hz), downward 128x128 RGB camera (0.80 rad HFOV), and downward 1D gpu_lidar (0.05–60 m)." },
      { path: "simulation/worlds/textured_field.sdf", role: "High-contrast PBR field with MarkerManager GUI plugin, launch helipad, spoofer_tx_station (-8, +8), and 12x12 m flight corridor." },
      { path: "simulation/airframes/4015_gz_x500_flow_lidar", role: "PX4 v1.15.4 custom airframe disabling internal GPSSIM (SENS_EN_GPSSIM=0) and enabling EKF2 multi-sensor fusion." },
      { path: "scripts/run_demo.sh", role: "Sequential showcase runner executing Stage 1/2 (Safe Nav OFF) followed by clean reset and Stage 2/2 (Safe Nav ON) on Leg 4." },
      { path: "analysis/run_experiments.py", role: "Runs 10 paired ablation episodes capturing both 20 Hz CSVs and raw PX4 binary .ulg flight logs into data/experiments/." },
      { path: "analysis/evaluate_experiments.py & plot_paper_figures.py", role: "Parses .ulg + CSV via pyulog to quantify cutover latency, excursion RMSE, settled hover drift, and 300-DPI paper plots." },
    ],
  },
];

export const MODERN_TOOLS = [
  { tool: "PX4 Autopilot v1.15.4 SITL", category: "Flight Stack & EKF2", justification: "Industry-standard open-source autopilot with configurable multi-sensor EKF2 (GPS, Optical Flow, downward rangefinder) and MAVLink/uXRCE-DDS telemetry." },
  { tool: "Gazebo Harmonic (gz-sim8) + Ogre2", category: "Physics & Sensor Sim", justification: "Provides GPU ray-traced 1D LiDAR scans, downward PBR camera frames for Lucas-Kanade optical flow, and real-time 3D MarkerManager visualization." },
  { tool: "ROS 2 Jazzy + Micro XRCE-DDS v2.4.3", category: "Robotics Middleware", justification: "Low-latency DDS transport mirroring onboard companion-computer <-> flight-controller messaging (px4_msgs release/1.15) at 20–50 Hz." },
  { tool: "OpenCV Lucas-Kanade + PyMAVLink", category: "Perception & Actuation", justification: "Extracts real pixel-level optical flow rates from downward imagery and executes sub-10 ms INT32 bit-packed EKF2 parameter overrides." },
  { tool: "Scikit-Learn + XGBoost + Joblib", category: "AI / ML Pipeline", justification: "Enables compact tree ensembles (<5 ms CPU inference, StratifiedGroupKFold leakage prevention) well-suited to embedded companion computers." },
  { tool: "PyULog + Matplotlib + Docker", category: "Verification & Reproducibility", justification: "Grounds ablation claims directly in PX4 internal binary .ulg estimator_status_flags logs inside a reproducible uav-gps-failsafe:jazzy container." },
];

// Review-1 Literature Review Matrix (Minimum 8 peer-reviewed papers, strictly sorted Latest to Oldest)
export const LITERATURE_MATRIX = [
  {
    citation: "D. Ou, J. J. Hagenaars, M. R. Jankowski et al. (2026) — \"Efficient robot navigation inspired by honeybee learning flights\", Nature",
    url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC13216067/",
    methodology: "Bio-inspired compact neural visual homing + path integration trained on small learning-flight regions.",
    findings: "Insect-scale visual homing reliably cancels accumulated path-integration drift without GPS fixes using tiny neural models (3.4–42 kB).",
    results: "Drone returned within 0.5 m of home on 100% of 30–110 m flights and 70% of 200–600 m outdoor flights in wind.",
    limitations: "Requires pre-explored visual homing context around origin; does not detect active cyber spoofing before drift begins.",
  },
  {
    citation: "A. Alsarhan, B. S. Khassawneh, M. AlJamal et al. (2026) — \"Multi-Layer AI Sensor System for Real-Time GPS Spoofing Detection and Encrypted UAS Control\", Sensors",
    url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC12899299/",
    methodology: "GPS Drift Index (GDI) preprocessing + Kalman filtering + quaternion filtering + DARTS lightweight neural search + PRESENT-128 encryption.",
    findings: "GDI + multi-sensor temporal consistency sharply isolates sneaky spoofing ramps while cryptographic C2 prevents command hijacking (1.79 ms overhead).",
    results: "High onboard detection separability across spoofing attacks with sub-2 ms cryptographic latency and 0.51 mJ energy cost.",
    limitations: "Requires hardware crypto integration on C2 radio link and neural architecture tuning; misses automated PX4 EKF2 GPS isolation.",
  },
  {
    citation: "K. Kose et al. (2026) — \"A UAV Testbed for Diagnosing Hardware Vulnerabilities: Quantifying Sim-to-Real Discrepancies in PX4 Flight Logs\", Sensors",
    url: "https://www.mdpi.com/1424-8220/26/10/3188",
    methodology: "Paired PX4 SITL vs. physical flight hardware logging pipeline analyzing ULog telemetry divergence.",
    findings: "Validates PX4 .ulg flight-log auditing as a reliable mechanism for diagnosing sensor anomalies and controller degradation.",
    results: "Quantifies specific sim-to-real variance bands across IMU and estimator flags in PX4 logs.",
    limitations: "Focuses on hardware anomaly diagnosis rather than closed-loop ML spoofing interception and EKF2 cutover.",
  },
  {
    citation: "Y. Zeng, Z. Lu, X. Zhao, Z. Xiao et al. (2025/2026) — \"GNSS Jamming and Spoofing Threats in UAV Navigation: Countermeasure Status and Challenges\", IEEE COMST",
    url: "https://ieeexplore.ieee.org/iel8/9739/5451756/11474471.pdf",
    methodology: "Comprehensive taxonomy across signal-level RF countermeasures, multi-antenna arrays, RAIM, and multi-sensor navigation.",
    findings: "Uncoordinated civilian L1 GPS lacks cryptographic authentication, requiring multi-layer sensor cross-validation.",
    results: "Synthesizes detection trade-offs across meaconing, synchronous spoofing, and multipath denial.",
    limitations: "Survey study without an integrated PX4 + Gazebo + ML autopilot recovery implementation.",
  },
  {
    citation: "M. Mouzai, M. A. Riahla, A. Keziou et al. (2025) — \"Exploring Multi-Channel GPS Receivers for Detecting Spoofing Attacks on UAVs Using Machine Learning\", Sensors",
    url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC12251763/",
    methodology: "Tree-based ML algorithms trained across multiple attack classes (simplistic, intermediate, sophisticated) on structured mission sequences.",
    findings: "Multi-attack evaluation reveals single-attack detectors fail to generalize across abrupt jumps vs. gradual drift profiles.",
    results: "Tree ensembles deliver high interpretability and real-time classification speed across diverse attack profiles.",
    limitations: "Relies on multi-channel RF receiver observables unavailable on standard Pixhawk HIL_GPS modules without self-contained backup odometry.",
  },
  {
    citation: "A. U. R. Badar, D. Mahmood, A. Iqbal et al. (2025) — \"DeepSpoofNet: A Framework for Securing UAVs Against GPS Spoofing Attacks\", PeerJ Computer Science",
    url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC11935755/",
    methodology: "Feature selection paired with oversampling and deep neural network classifiers for telemetry-level GPS spoofing detection.",
    findings: "Addressing severe nominal/attack class imbalance and non-redundant feature selection sharply reduces false alarms.",
    results: "Demonstrates strong F1 recovery across unbalanced UAV telemetry datasets.",
    limitations: "Higher inference footprint than lightweight tree ensembles and lacks automated autopilot failover actuator integration.",
  },
  {
    citation: "M. Arora, P. Shukla, S. Chopra (2025) — \"A Compendium of Autonomous Navigation using Object Detection and Tracking in UAVs\", arXiv:2506.05378",
    url: "https://arxiv.org/pdf/2506.05378",
    methodology: "Review of real-time computer vision, visual odometry, and onboard tracking pipelines for urban autonomous drones.",
    findings: "Lightweight onboard visual cues bridge transient GPS denial in structured last-mile corridors.",
    results: "Catalogs latency vs accuracy constraints for edge-compute companion boards.",
    limitations: "GPU-heavy object trackers impose power penalties compared to sparse Lucas-Kanade downward optical flow.",
  },
  {
    citation: "T. Mina, A. Kanhere, A. Shetty, G. Gao (2024) — \"GPS Spoofing-Resilient Filtering Using Self-Contained Sensors and Chimera Signal Enhancement\", NAVIGATION",
    url: "https://navi.ion.org/content/71/2/navi.636",
    methodology: "Coupled EKF state estimation combining IMU / wheel-odometry self-contained sensors with Chimera NMA authentication.",
    findings: "Tight coupling with self-contained sensors prevents unbounded EKF divergence between sparse GNSS authentication epochs.",
    results: "Bounds localization error under sustained GNSS spoofing using self-contained motion priors.",
    limitations: "Chimera satellite signal authentication is not yet widely supported on low-cost civilian UAV receivers.",
  },
  {
    citation: "J. Flores, I. Gonzalez-Hernandez, S. Salazar (2024) — \"Improving Optical Flow Sensor Using a Gimbal for Quadrotor Navigation in GPS-Denied Environment\", Sensors",
    url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC11014312/",
    methodology: "Downward optical flow camera paired with 6-DoF IMU and attitude-decoupling stabilization for GPS-denied hover.",
    findings: "Decoupling rotational body rates (gyro compensation) is essential so quadrotor pitch/roll corrections do not inject false translation velocity.",
    results: "Significantly improves GPS-denied velocity and position hold stability under aggressive hover disturbances.",
    limitations: "Focuses strictly on mechanical/control optical-flow hover; lacks cyber-attack detection to decide when to cut GPS.",
  },
  {
    citation: "A. Altaweel et al. (2023) — \"GPS Spoofing Attacks in FANETs: A Systematic Literature Review\", IEEE Access",
    url: "https://www.researchgate.net/publication/371183823_GPS_Spoofing_Attacks_in_FANETs_A_Systematic_Literature_Review",
    methodology: "Systematic literature synthesis of civilian GNSS spoofing vectors, RSS/inertial cross-checks, and simulation frameworks.",
    findings: "Coordinated takeover attacks exploit EKF innovation gating specifically by keeping instantaneous step residuals below static Chi-square thresholds.",
    results: "Identifies temporal sliding-window anomaly fusion + physical sensor redundancy as key open gaps.",
    limitations: "Review-level taxonomy without executable PX4 SITL recovery benchmarks.",
  },
  {
    citation: "C. Deng, C.-H. J. Wang, K. H. Low (2022) — \"Investigation of Using Sky Openness Ratio as Predictor for Navigation Performance in Urban Environment\", Sensors",
    url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC8838107/",
    methodology: "Real flight experiments across open carparks, building canyons, and glass-clad facades comparing RTK ground truth against GPS EPH.",
    findings: "Receiver-reported horizontal uncertainty (EPH) shows no reliable correlation with actual horizontal multipath/urban positioning error.",
    results: "Quantifies urban-canyon lateral navigation degradation where sky visibility drops.",
    limitations: "Proves EPH alone cannot serve as a failsafe trigger against degraded or spoofed GNSS fixes.",
  },
  {
    citation: "N. Gu, F. Xing, Z. You (2021) — \"GNSS Spoofing Detection Based on Coupled Visual/Inertial/GNSS Navigation System\", Sensors",
    url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC8539116/",
    methodology: "Tightly coupled Visual-Inertial Odometry (VIO) + GNSS optimization factor graph with modified Chi-square anomaly detection.",
    findings: "Even coupled VIO/GNSS filters get slowly pulled off course if GNSS spoofing bypasses residual thresholds before isolation occurs.",
    results: "Modified Chi-square detector isolates subtle deviations and preserves safe navigation using visual-inertial dead reckoning.",
    limitations: "Static Chi-square thresholds struggle to simultaneously maximize recall on 4 m step jumps and zero false alarms during agile turns.",
  },
];

// Full 7-category Research Paper Library preserving all 41 user-referenced URLs
export const RESEARCH_CATEGORIES = [
  {
    category: "1. GNSS Limitations & Urban Canyons",
    summary: "Analyzes multipath, NLOS errors, sky openness degradation, and why receiver-reported EPH fails in cluttered urban environments.",
    papers: [
      { title: "Investigation of Using Sky Openness Ratio as Predictor for Navigation Performance in Urban Environment (Sensors, 2022)", url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC8838107/", role: "Demonstrates EPH unreliability vs RTK ground truth." },
      { title: "3D LiDAR Aided GNSS NLOS Mitigation in Urban Canyons (arXiv:2112.06108, 2021)", url: "https://arxiv.org/pdf/2112.06108", role: "Quantifies urban canyon NLOS GNSS exclusion using LiDAR." },
      { title: "Low-Cost GNSS and PPP-RTK: Capabilities of u-blox ZED-F9P (Sensors, Vol. 23, 2023)", url: "https://www.mdpi.com/1424-8220/23/13/6074", role: "Benchmarks tactical civilian GNSS accuracy & convergence limits." },
      { title: "Deep Reinforcement Learning for Vision-Based Navigation Avoiding Obstacles (Drones, Vol. 7, 2023)", url: "https://www.mdpi.com/2504-446X/7/4/245", role: "Explores vision-assisted urban autonomy under weak GNSS." },
      { title: "Multiple Drone Navigation & Formation Using Selective Target Tracking Vision (Electronics, Vol. 10, 2021)", url: "https://www.mdpi.com/2079-9292/10/17/2125", role: "Vision fallback coordination in GNSS-challenged terrain." },
      { title: "GNSS Localization-Based Path Planning Algorithm for UAV Navigation (SciSpace PDF)", url: "https://scispace.com/pdf/a-new-path-planning-algorithm-using-a-gnss-localization-hw9d24i5y5.pdf", role: "Analyzes localization-aware path constraints under GNSS uncertainty." },
      { title: "GNSS Degradation & Urban UAV Localization Reliability Study (Semantic Scholar PDF)", url: "https://pdfs.semanticscholar.org/3b1e/067fd224ff4b0361a4b20c6d9870e28994c4.pdf", role: "Supporting study on urban GNSS signal vulnerability." },
    ],
  },
  {
    category: "2. Cyber-Security: Jamming & Spoofing",
    summary: "Catalogs RF interference, meaconing, step jumps, and smooth coordinated spoofing threats against unencrypted civilian UAV receivers.",
    papers: [
      { title: "GNSS Jamming and Spoofing Threats in UAV Navigation: Countermeasure Status and Challenges (IEEE COMST)", url: "https://ieeexplore.ieee.org/iel8/9739/5451756/11474471.pdf", role: "Comprehensive survey of jamming, spoofing, and countermeasure architectures." },
      { title: "GNSS Spoofing Attacks and Countermeasures in Unmanned / Missile Systems: Scoping Review (MDPI, Vol. 15)", url: "https://www.mdpi.com/2073-431x/15/10/648", role: "Threat taxonomy across RF & navigation layers." },
      { title: "Research on GNSS Spoofing Detection and Autonomous Positioning for Drones (Electronics, Vol. 14)", url: "https://www.mdpi.com/2079-9292/14/15/3147", role: "Recent electronics-layer UAV GNSS spoofing defense study." },
      { title: "GNSS Anti-Interference Technologies for Unmanned Systems: A Brief Review (2025)", url: "https://www.researchgate.net/publication/391445805_GNSS_Anti-Interference_Technologies_for_Unmanned_Systems_A_Brief_Review", role: "Surveys antenna, spatial nulling, and sensor-level mitigation." },
      { title: "A Systematic Literature Review on Spoofing & Jamming in UAV Navigation (JATM)", url: "https://jatm.com.br/jatm/article/download/1396/1066/6384", role: "Aerospace categorization of spoofing attack profiles." },
      { title: "GPS Spoofing Attacks in FANETs: A Systematic Literature Review (IEEE Access, 2023)", url: "https://www.researchgate.net/publication/371183823_GPS_Spoofing_Attacks_in_FANETs_A_Systematic_Literature_Review", role: "Identifies covert slow-drift takeover risks past static EKF gates." },
      { title: "IEEE Xplore Study on GNSS Interference & Spoofing Countermeasures (Doc 10139317)", url: "https://ieeexplore.ieee.org/iel7/6287639/10005208/10139317.pdf", role: "Evaluates receiver-level anomaly detection benchmarks." },
    ],
  },
  {
    category: "3. Mathematical Detection (EKF)",
    summary: "Establishes Kalman innovation residual tests, multi-receiver consistency, and why pure static thresholds leave blind spots.",
    papers: [
      { title: "GPS Spoofing-Resilient Filtering Using Self-Contained Sensors and Chimera Enhancement (NAVIGATION, 2024)", url: "https://navi.ion.org/content/71/2/navi.636", role: "Motivated fusing self-contained inertial/flow kinematics against spoofing." },
      { title: "LiDAR-Based Terrain-Relative Autonomous Takeoff & Landing in GNSS-Degraded Environments (Drones, Vol. 10)", url: "https://www.mdpi.com/2504-446X/10/8/559", role: "Highlights LiDAR height resilience when GNSS altitude degrades." },
      { title: "Results on GNSS Spoofing Mitigation Using Multiple Receivers (NAVIGATION, 2022)", url: "https://navi.ion.org/content/69/1/navi.510", role: "Baseline spatial consistency approach across dual receivers." },
      { title: "GNSS Spoofing Detection Based on Coupled Visual/Inertial/GNSS System (Sensors, 2021)", url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC8539116/", role: "Demonstrated modified Chi-square alarm & VIO isolation." },
    ],
  },
  {
    category: "4. Machine Learning Detection Pipelines",
    summary: "Directly informed our 24-feature sliding window, GPS Drift Index (gdi_net_xy), StratifiedGroupKFold leakage guard, and RF/XGBoost ensemble.",
    papers: [
      { title: "Multi-Layer AI Sensor System for Real-Time GPS Spoofing Detection and Encrypted UAS Control (Sensors, 2026)", url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC12899299/", role: "Inspired GDI (GPS Drift Index) + temporal telemetry consistency features." },
      { title: "DeepSpoofNet: Securing UAVs Against GPS Spoofing Attacks (PeerJ CS, 2025)", url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC11935755/", role: "Guided class-balanced training & feature selection." },
      { title: "Exploring Multi-Channel GPS Receivers for Detecting Spoofing Attacks Using ML (Sensors, 2025)", url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC12251763/", role: "Validated tree-based ML generalization across multiple attack types." },
      { title: "A Systematic Review of Machine Learning Techniques for GNSS Use Cases", url: "https://www.scribd.com/document/705173964/A-Systematic-Review-of-Machine-Learning-Techniques-for-GNSS-Use-Cases", role: "Surveys classical vs deep ML detectors on GNSS observables." },
    ],
  },
  {
    category: "5. Optical Flow & LiDAR Odometry (GPS-Denied)",
    summary: "Establishes gyro-compensated Lucas-Kanade optical flow velocity reconstruction and downward 1D LiDAR altitude scaling.",
    papers: [
      { title: "Efficient Robot Navigation Inspired by Honeybee Learning Flights (Nature, 2026)", url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC13216067/", role: "Demonstrates lightweight GPS-free visual homing & return-to-home." },
      { title: "An Edge-Computing UAV Architecture for GPS-Denied Structural Inspection (Drones, Vol. 10)", url: "https://www.mdpi.com/2504-446X/10/9/678", role: "Edge-compute sensor integration for concrete GNSS-denied corridors." },
      { title: "Accelerometer Bias Estimation Using EKF-Based Vision-Aided Navigation (Electronics, Vol. 14)", url: "https://www.mdpi.com/2079-9292/14/6/1074", role: "Quantifies EKF fusion of IMU + altimeter + optical flow without GPS." },
      { title: "Improving Optical Flow Sensor Using a Gimbal for Quadrotor GPS-Denied Navigation (Sensors, 2024)", url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC11014312/", role: "Motivated gyro-rate compensation formula in flow_to_ned_velocity()." },
      { title: "Optical Flow Information Fusion Study (ISIF, 2025)", url: "https://isif.org/files/isif/2025-01/optical_flow_p72.pdf", role: "Estimation-theoretic optical flow velocity fusion." },
      { title: "When Being Soft Makes You Tough: Collision-Resilient Quadcopter Inspired by Exoskeletons", url: "https://www.researchgate.net/publication/349913718_When_Being_Soft_Makes_You_Tough_A_Collision_Resilient_Quadcopter_Inspired_by_Arthropod_Exoskeletons", role: "Physical resilience context for indoor/GPS-denied flight." },
    ],
  },
  {
    category: "6. Urban Logistics & Vision Systems",
    summary: "Provides operational motivation from last-mile drone delivery, patrolling, and real-time edge vision architectures.",
    papers: [
      { title: "A Compendium of Autonomous Navigation using Object Detection and Tracking in UAVs (arXiv:2506.05378, 2025)", url: "https://arxiv.org/pdf/2506.05378", role: "Modern urban logistics & edge vision survey." },
      { title: "Intelligent Drone Patrolling with Real-Time Object Detection and Path Adaptation (Eng. Proc., MDPI)", url: "https://www.mdpi.com/2673-4591/124/1/82", role: "Real-world autonomous corridor patrol architecture." },
      { title: "Autonomous Drone Racing: A Survey (arXiv:2301.01755, 2023)", url: "https://arxiv.org/html/2301.01755v4", role: "Benchmarks agile state estimation & low-latency onboard flight control." },
      { title: "IoT Deep Learning UAV Systems for Autonomous Obstacle Detection (Remote Sensing, Vol. 11)", url: "https://www.mdpi.com/2072-4292/11/18/2144", role: "Companion-computer latency constraints for onboard AI." },
      { title: "The Urban Last Mile Problem: Autonomous Drone Delivery to Your Balcony (arXiv:1809.08022v1, 2018)", url: "https://arxiv.org/html/1809.08022v1", role: "Motivates safe GPS-denied hover near urban buildings." },
      { title: "Urban Last Mile Delivery (Semantic Scholar Record — Brunner, Szebedy et al.)", url: "https://www.semanticscholar.org/paper/The-Urban-Last-Mile-Problem%3A-Autonomous-Drone-to-Brunner-Szebedy/cbfb84d98f23520466759273fcfd3f05218fb57f", role: "Indexed citation record for urban drone delivery." },
      { title: "The Urban Last Mile Problem (arXiv:1809.08022 Abstract Mirror)", url: "https://arxiv.org/abs/1809.08022", role: "Canonical arXiv abstract link matching arXiv:1809.08022v1." },
    ],
  },
  {
    category: "7. Simulation Frameworks (PX4 / Gazebo) & Datasets",
    summary: "Establishes reproducible PX4 SITL + Gazebo architectures, sim-to-real PX4 ULog verification, and intrusion dataset design standards.",
    papers: [
      { title: "A UAV Testbed for Diagnosing Hardware Vulnerabilities: Quantifying Sim-to-Real Discrepancies in PX4 Flight Logs (Sensors, Vol. 26)", url: "https://www.mdpi.com/1424-8220/26/10/3188", role: "Supports PX4 .ulg audit pipeline in evaluate_experiments.py." },
      { title: "A Comprehensive Literature Review on Intrusion Detection Datasets for UAVs (ResearchGate)", url: "https://www.researchgate.net/publication/403252578_A_comprehensive_literature_review_on_intrusion_detection_datasets_for_UAVs_taxonomy_challenges_future_directions_and_recommendations", role: "Justifies episode-isolated labeling without train/test leakage." },
      { title: "Autonomous UAV Simulation Platform Thesis (UnB BDM, 2025 — Renato Britto Araujo)", url: "https://bdm.unb.br/bitstream/10483/42664/1/2025_RenatoBrittoAraujo_tcc.pdf", role: "Recent containerized PX4/Gazebo academic simulation methodology." },
      { title: "IEEE Xplore UAV Simulation & Intrusion Resilience Study (Doc 11680531)", url: "https://ieeexplore.ieee.org/iel8/8782706/8955964/11680531.pdf", role: "Simulation-driven flight control & anomaly verification." },
      { title: "Security in Internet of Drones: A Comprehensive Review (Cogent Engineering, 2022)", url: "https://www.tandfonline.com/doi/full/10.1080/23311916.2022.2029080", role: "Reviews IoD simulators and attack testbeds." },
      { title: "Pixhawk PX-4 Autopilot in Control of a Small UAV (Semantic Scholar — Lesko, Schreiner)", url: "https://www.semanticscholar.org/paper/Pixhawk-PX-4-Autopilot-in-Control-of-a-Small-Le%C5%A1ko-Schreiner/cdeccf323fe3404635595c47f554a243ef77480c", role: "Foundational PX4 autopilot SITL/HIL integration reference." },
    ],
  },
];

export const IEEE_REFERENCES = [
  "[1] D. Ou, J. J. Hagenaars, M. R. Jankowski, et al., \"Efficient robot navigation inspired by honeybee learning flights,\" Nature (PMC13216067), 2026.",
  "[2] A. Alsarhan, B. S. Khassawneh, M. AlJamal, et al., \"Multi-Layer AI Sensor System for Real-Time GPS Spoofing Detection and Encrypted UAS Control,\" Sensors (PMC12899299), 2026.",
  "[3] K. Kose et al., \"A UAV Testbed for Diagnosing Hardware Vulnerabilities: Quantifying Sim-to-Real Discrepancies in PX4 Flight Logs,\" Sensors, vol. 26, no. 10, p. 3188, 2026.",
  "[4] Y. Zeng, Z. Lu, X. Zhao, Z. Xiao, S. Ni, Z. Han, and K. Li, \"GNSS Jamming and Spoofing Threats in UAV Navigation: Countermeasure Status and Challenges,\" IEEE Communications Surveys & Tutorials (Doc 11474471).",
  "[5] M. Mouzai, M. A. Riahla, A. Keziou, et al., \"Exploring Multi-Channel GPS Receivers for Detecting Spoofing Attacks on UAVs Using Machine Learning,\" Sensors (PMC12251763), 2025.",
  "[6] A. U. R. Badar, D. Mahmood, A. Iqbal, et al., \"DeepSpoofNet: a framework for securing UAVs against GPS spoofing attacks,\" PeerJ Computer Science (PMC11935755), 2025.",
  "[7] M. Arora, P. Shukla, and S. Chopra, \"A Compendium of Autonomous Navigation using Object Detection and Tracking in Unmanned Aerial Vehicles,\" arXiv:2506.05378, 2025.",
  "[8] T. Mina, A. Kanhere, A. Shetty, and G. Gao, \"GPS Spoofing-Resilient Filtering Using Self-Contained Sensors and Chimera Signal Enhancement,\" NAVIGATION, vol. 71, no. 2, navi.636, 2024.",
  "[9] J. Flores, I. Gonzalez-Hernandez, and S. Salazar, \"Improving Optical Flow Sensor Using a Gimbal for Quadrotor Navigation in GPS-Denied Environment,\" Sensors (PMC11014312), 2024.",
  "[10] A. Altaweel et al., \"GPS Spoofing Attacks in FANETs: A Systematic Literature Review,\" IEEE Access (DOI: 10.1109/ACCESS.2023.3281731), 2023.",
  "[11] C. Deng, C.-H. J. Wang, and K. H. Low, \"Investigation of Using Sky Openness Ratio as Predictor for Navigation Performance in Urban-like Environment to Support PBN in UTM,\" Sensors (PMC8838107), 2022.",
  "[12] N. Gu, F. Xing, and Z. You, \"GNSS Spoofing Detection Based on Coupled Visual/Inertial/GNSS Navigation System,\" Sensors (PMC8539116), 2021.",
];

export const COURSE_OUTCOMES = [
  { co: "CO1", statement: "Conduct a structured literature review and identify research gaps for identifying complex engineering problems.", wk: "WK1-5, WK7-8", po: "PO1, PO2, PO4, PO6" },
  { co: "CO2", statement: "Formulate a clear problem statement, define feasible objectives and scope for the identified problem.", wk: "WK2, WK3, WK4", po: "PO2" },
  { co: "CO3", statement: "Design high level and low level to integrate various modules using effective design principles and practices.", wk: "WK1-4, WK5-7", po: "PO1, PO3, PO6" },
  { co: "CO4", statement: "Apply modern AI related tools, frameworks, and engineering technologies with relevant experiments, testing and performance metrics evaluation.", wk: "WK2, WK6", po: "PO5" },
  { co: "CO5", statement: "Adhere to ethical principles and demonstrate professional conduct.", wk: "WK9", po: "PO7" },
  { co: "CO6", statement: "Prepare structured technical reports, design documentation, and deliver effective presentations while functioning as responsible team member.", wk: "—", po: "PO8, PO9" },
  { co: "CO7", statement: "Practice project management principles, plan resources efficiently, adapt to emerging tools/technologies, and demonstrate lifelong learning skills.", wk: "WK8", po: "PO10, PO11" },
];

export const EVALUATION_RUBRICS = [
  {
    rubric: "Rubric 1 — Literature Survey (CO1)",
    maxMarks: "10M",
    excellentCriteria: "In-depth analysis and synthesis are done on most & recent relevant literature.",
    projectFulfillment: "12 latest-to-oldest peer-reviewed papers synthesized (2026 → 2021) + full 41-reference categorized library with explicit limitation mapping.",
  },
  {
    rubric: "Rubric 2 — Problem Formulation, Objectives & Scope (CO2)",
    maxMarks: "5M",
    excellentCriteria: "The problem is clearly formulated with well bounded objectives and scope that are achievable & time-bound.",
    projectFulfillment: "3 bounded objectives covering SITL digital twin, leakage-free 24-feature AI detection, and real-time EKF2 GPS-denied failover with explicit boundaries.",
  },
  {
    rubric: "Rubric 3 — Design: High & Low Levels (CO3)",
    maxMarks: "10M",
    excellentCriteria: "Provides a clear, structured, and accurate system architecture with well-defined modules, data flow, and interactions.",
    projectFulfillment: "Explicit HLD bus diagram (Gazebo, PX4 EKF2, ROS 2 uXRCE-DDS, MAVLink UDP 14030/13030/14540) + LLD 20 Hz FeatureWindowExtractor & failover state machine.",
  },
  {
    rubric: "Rubric 4 — Modern Tools Identification (CO4)",
    maxMarks: "5M",
    excellentCriteria: "Identifies the most appropriate and up-to-date modern tools, technologies, frameworks, and platforms.",
    projectFulfillment: "PX4 v1.15.4, Gazebo Harmonic, ROS 2 Jazzy, Micro XRCE-DDS v2.4.3, OpenCV Lucas-Kanade, Scikit-Learn, XGBoost, PyMAVLink, PyULog, Docker, Vercel.",
  },
];

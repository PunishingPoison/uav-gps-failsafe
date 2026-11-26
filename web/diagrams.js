// Procedural vector SVG architecture, low-level pipeline, and control physics diagrams.

export function renderHldDiagramSvg() {
  return `
  <svg viewBox="0 0 1180 510" class="diagram-svg" role="img" aria-label="High-Level System Architecture Diagram">
    <defs>
      <marker id="arr-ink" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,1 L7,4 L0,7 Z" fill="#18232E"/>
      </marker>
      <marker id="arr-cobalt" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,1 L7,4 L0,7 Z" fill="#1B5299"/>
      </marker>
      <marker id="arr-carmine" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,1 L7,4 L0,7 Z" fill="#B43427"/>
      </marker>
      <marker id="arr-emerald" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,1 L7,4 L0,7 Z" fill="#166B48"/>
      </marker>
    </defs>

    <!-- Background Zone Bands with generous 54px inter-column channels for bus labels -->
    <rect x="12" y="16" width="242" height="478" rx="8" fill="#EDE8DC" stroke="#D8D0C1" stroke-width="1.2"/>
    <text x="26" y="40" class="svg-zone-title">1. Gazebo Harmonic Twin</text>

    <rect x="308" y="16" width="248" height="478" rx="8" fill="#FCFBF7" stroke="#D8D0C1" stroke-width="1.2"/>
    <text x="322" y="40" class="svg-zone-title">2. Sensor &amp; Threat Layer (ROS 2)</text>

    <rect x="626" y="16" width="224" height="478" rx="8" fill="#EDE8DC" stroke="#1B5299" stroke-width="1.4"/>
    <text x="640" y="40" class="svg-zone-title" fill="#1B5299">3. PX4 SITL v1.15.4 Core</text>

    <rect x="920" y="16" width="248" height="478" rx="8" fill="#FCFBF7" stroke="#166B48" stroke-width="1.4"/>
    <text x="934" y="40" class="svg-zone-title" fill="#166B48">4. AI Guardian &amp; Autonomy</text>

    <!-- Zone 1 Nodes -->
    <rect x="24" y="58" width="218" height="98" rx="6" fill="#FCFBF7" stroke="#18232E" stroke-width="1.2"/>
    <text x="36" y="80" class="svg-box-title">x500_flow_lidar SDF</text>
    <text x="36" y="99" class="svg-box-sub">Airframe 4015 (GPSSIM disabled)</text>
    <text x="36" y="117" class="svg-box-sub">Downward Cam: 128x128 RGB @ 30 Hz</text>
    <text x="36" y="135" class="svg-box-sub">1D LiDAR: 0.05-60 m @ 30 Hz</text>

    <rect x="24" y="174" width="218" height="74" rx="6" fill="#FCFBF7" stroke="#18232E" stroke-width="1.2"/>
    <text x="36" y="196" class="svg-box-title">textured_field.sdf World</text>
    <text x="36" y="215" class="svg-box-sub">High-contrast PBR optical surface</text>
    <text x="36" y="233" class="svg-box-sub">12x12 m square + MarkerManager</text>

    <rect x="24" y="266" width="218" height="74" rx="6" fill="#FAF0EE" stroke="#B43427" stroke-width="1.3"/>
    <text x="36" y="288" class="svg-box-title" fill="#B43427">spoofer_tx_station</text>
    <text x="36" y="307" class="svg-box-sub">Rogue TX at (-8.0, +8.0) ENU</text>
    <text x="36" y="325" class="svg-box-sub">Visual RF beacon + beam origin</text>

    <rect x="24" y="358" width="218" height="118" rx="6" fill="#FCFBF7" stroke="#4F5D6B" stroke-width="1.1"/>
    <text x="36" y="382" class="svg-box-title">ros_gz_bridge</text>
    <text x="36" y="403" class="svg-box-sub">/gz/downward_camera/image</text>
    <text x="36" y="421" class="svg-box-sub">/gz/downward_lidar/scan</text>
    <text x="36" y="439" class="svg-box-sub">/gz/navsat</text>
    <text x="36" y="457" class="svg-box-sub">/gz/ground_truth/odom (50 Hz)</text>

    <!-- Zone 2 Nodes -->
    <rect x="320" y="58" width="224" height="174" rx="6" fill="#F4F7FB" stroke="#1B5299" stroke-width="1.4"/>
    <text x="334" y="81" class="svg-box-title" fill="#1B5299">sensor_bridge_node</text>
    <text x="334" y="103" class="svg-box-sub">• OpenCV Lucas-Kanade Flow</text>
    <text x="334" y="121" class="svg-box-sub">  -> OPTICAL_FLOW_RAD (30 Hz)</text>
    <text x="334" y="141" class="svg-box-sub">• 1D LiDAR -> DISTANCE_SENSOR</text>
    <text x="334" y="161" class="svg-box-sub">• Nominal HIL_GPS (UDP 14030)</text>
    <text x="334" y="181" class="svg-box-sub">• Publishes /uav/optical_flow</text>
    <text x="334" y="199" class="svg-box-sub">  and /uav/ground_truth_odom</text>

    <rect x="320" y="256" width="224" height="220" rx="6" fill="#FAF0EE" stroke="#B43427" stroke-width="1.4"/>
    <text x="334" y="280" class="svg-box-title" fill="#B43427">adversary_spoofer_node</text>
    <text x="334" y="303" class="svg-box-sub">1. Sets /adversary/active = True</text>
    <text x="334" y="321" class="svg-box-sub">   (preempts sensor_bridge GPS)</text>
    <text x="334" y="343" class="svg-box-sub">2. Injects spoofed HIL_GPS packets</text>
    <text x="334" y="361" class="svg-box-sub">   on UDP 13030 at 10 Hz:</text>
    <text x="334" y="381" class="svg-box-sub">   - Step jump (offset N / E)</text>
    <text x="334" y="399" class="svg-box-sub">   - Slow drift / meaconing ramp</text>
    <text x="334" y="417" class="svg-box-sub">   - S-curve coordinated takeover</text>
    <text x="334" y="441" class="svg-box-sub">3. Logs /adversary/attack_status</text>

    <!-- Zone 3 Nodes -->
    <rect x="638" y="58" width="200" height="162" rx="6" fill="#FCFBF7" stroke="#1B5299" stroke-width="1.5"/>
    <text x="650" y="81" class="svg-box-title" fill="#1B5299">PX4 EKF2 Estimator</text>
    <text x="650" y="103" class="svg-box-sub">Fuses GPS + OF + LiDAR + IMU</text>
    <text x="650" y="123" class="svg-box-sub">Outputs estimator_status_flags</text>
    <text x="650" y="141" class="svg-box-sub">(cs_gps, cs_opt_flow, cs_rng)</text>
    <text x="650" y="163" class="svg-box-sub">Runtime Parameter Switching:</text>
    <text x="650" y="181" class="svg-box-sub">EKF2_GPS_CTRL, EKF2_HGT_REF</text>
    <text x="650" y="199" class="svg-box-sub">EKF2_OF_CTRL, EKF2_RNG_CTRL</text>

    <rect x="638" y="238" width="200" height="92" rx="6" fill="#FCFBF7" stroke="#18232E" stroke-width="1.2"/>
    <text x="650" y="261" class="svg-box-title">MC Position Control</text>
    <text x="650" y="281" class="svg-box-sub">OFFBOARD TrajectorySetpoint</text>
    <text x="650" y="299" class="svg-box-sub">vs. AUTO.LOITER Safe Hover</text>
    <text x="650" y="317" class="svg-box-sub">Writes binary .ulg flight log</text>

    <rect x="638" y="348" width="200" height="128" rx="6" fill="#FCFBF7" stroke="#18232E" stroke-width="1.2"/>
    <text x="650" y="372" class="svg-box-title">uXRCE-DDS v2.4.3</text>
    <text x="650" y="394" class="svg-box-sub">Bidirectional ROS 2 topics:</text>
    <text x="650" y="414" class="svg-box-sub">/fmu/out/vehicle_gps_position</text>
    <text x="650" y="432" class="svg-box-sub">/fmu/out/vehicle_local_position</text>
    <text x="650" y="450" class="svg-box-sub">/fmu/in/vehicle_command</text>

    <!-- Zone 4 Nodes -->
    <rect x="932" y="58" width="224" height="148" rx="6" fill="#EEF7F2" stroke="#166B48" stroke-width="1.6"/>
    <text x="946" y="81" class="svg-box-title" fill="#166B48">guardian_ai_node (20 Hz)</text>
    <text x="946" y="103" class="svg-box-sub">• Causal 24-feature window</text>
    <text x="946" y="121" class="svg-box-sub">• RF / XGBoost inference (&lt;5 ms)</text>
    <text x="946" y="141" class="svg-box-sub">• Atomic MAVLink UDP 14540:</text>
    <text x="946" y="159" class="svg-box-sub">  EKF2_GPS_CTRL=0 + HOLD</text>
    <text x="946" y="179" class="svg-box-sub">• Publishes /guardian/failover</text>

    <rect x="932" y="228" width="224" height="96" rx="6" fill="#FCFBF7" stroke="#18232E" stroke-width="1.2"/>
    <text x="946" y="252" class="svg-box-title">mission_runner_node</text>
    <text x="946" y="273" class="svg-box-sub">12x12 m Square (WP1..WP4)</text>
    <text x="946" y="291" class="svg-box-sub">Yields Offboard setpoints when</text>
    <text x="946" y="309" class="svg-box-sub">/guardian/failover_active = True</text>

    <rect x="932" y="344" width="224" height="132" rx="6" fill="#FCFBF7" stroke="#4F5D6B" stroke-width="1.1"/>
    <text x="946" y="368" class="svg-box-title">Telemetry &amp; Tactical HUD</text>
    <text x="946" y="390" class="svg-box-sub">• demo_hud_node: Gazebo 3D</text>
    <text x="946" y="408" class="svg-box-sub">  (/marker_array) + 820x820 HUD</text>
    <text x="946" y="428" class="svg-box-sub">• telemetry_logger_node: 20 Hz</text>
    <text x="946" y="446" class="svg-box-sub">  CSV (74 cols) for ml &amp; ablation</text>

    <!-- Connecting Edges cleanly routed inside 54-70px inter-zone gaps -->
    <path d="M242,412 L278,412 L278,150 L320,150" stroke="#1B5299" stroke-width="1.8" fill="none" marker-end="url(#arr-cobalt)"/>
    <text x="256" y="280" class="svg-edge-label" fill="#1B5299" transform="rotate(-90 256 280)">ROS Sensors</text>

    <path d="M432,232 L432,256" stroke="#B43427" stroke-width="1.6" stroke-dasharray="4,3" fill="none" marker-end="url(#arr-carmine)"/>

    <!-- Sensor/Spoof MAVLink to PX4 (Zone 2 -> Zone 3 channel x=556..626) -->
    <path d="M544,132 L638,132" stroke="#1B5299" stroke-width="2.0" fill="none" marker-end="url(#arr-cobalt)"/>
    <text x="556" y="121" class="svg-edge-label" fill="#1B5299">UDP 14030</text>

    <path d="M544,348 L568,348 L568,184 L638,184" stroke="#B43427" stroke-width="2.0" fill="none" marker-end="url(#arr-carmine)"/>
    <text x="574" y="173" class="svg-edge-label" fill="#B43427">UDP 13030</text>

    <!-- PX4 DDS to Zone 4 (Zone 3 -> Zone 4 channel x=850..920) -->
    <path d="M838,412 L884,412 L884,142 L932,142" stroke="#18232E" stroke-width="1.6" fill="none" marker-end="url(#arr-ink)"/>
    <path d="M838,412 L884,412 L884,276 L932,276" stroke="#18232E" stroke-width="1.6" fill="none" marker-end="url(#arr-ink)"/>
    <path d="M838,412 L932,412" stroke="#18232E" stroke-width="1.6" fill="none" marker-end="url(#arr-ink)"/>

    <!-- Guardian Override back to PX4 (above EKF2 line cleanly inside Zone 3-4 gap) -->
    <path d="M932,96 L838,96" stroke="#166B48" stroke-width="2.2" fill="none" marker-end="url(#arr-emerald)"/>
    <text x="849" y="84" class="svg-edge-label" fill="#166B48">UDP 14540</text>
    <text x="849" y="111" class="svg-edge-label" fill="#166B48">PARAM_SET</text>

    <!-- Failover preemption to mission runner -->
    <path d="M1044,206 L1044,228" stroke="#166B48" stroke-width="1.8" fill="none" marker-end="url(#arr-emerald)"/>
  </svg>`;
}

export function renderLldDiagramSvg() {
  return `
  <svg viewBox="0 0 1160 440" class="diagram-svg" role="img" aria-label="Low-Level AI Detection &amp; Failover State Machine Diagram">
    <defs>
      <marker id="lld-ink" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,1 L7,4 L0,7 Z" fill="#18232E"/>
      </marker>
      <marker id="lld-em" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,1 L7,4 L0,7 Z" fill="#166B48"/>
      </marker>
      <marker id="lld-car" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,1 L7,4 L0,7 Z" fill="#B43427"/>
      </marker>
    </defs>

    <!-- Top Strip: 20 Hz Inference Pipeline -->
    <text x="16" y="28" class="svg-zone-title">A. Online 20 Hz Cross-Sensor Feature &amp; Detection Pipeline (guardian_ai_node + feature_extractor.py)</text>

    <rect x="16" y="44" width="225" height="154" rx="6" fill="#FCFBF7" stroke="#18232E" stroke-width="1.3"/>
    <text x="28" y="66" class="svg-box-title">1. Onboard Inputs (20 Hz)</text>
    <text x="28" y="87" class="svg-box-sub">/fmu/out/vehicle_gps_position</text>
    <text x="28" y="105" class="svg-box-sub">/fmu/out/vehicle_local_position</text>
    <text x="28" y="123" class="svg-box-sub">/fmu/out/sensor_combined (IMU)</text>
    <text x="28" y="141" class="svg-box-sub">/fmu/out/vehicle_attitude (q)</text>
    <text x="28" y="159" class="svg-box-sub">/uav/optical_flow (flow, range)</text>
    <text x="28" y="182" class="svg-box-sub" fill="#B43427">Zero gt_* or spoof_* inputs</text>

    <rect x="275" y="44" width="275" height="154" rx="6" fill="#EDE8DC" stroke="#1B5299" stroke-width="1.4"/>
    <text x="288" y="66" class="svg-box-title" fill="#1B5299">2. FeatureWindowExtractor</text>
    <text x="288" y="86" class="svg-box-sub">Circular Buffer: W=20 (1.0 s), min=10</text>
    <text x="288" y="106" class="svg-box-sub">• GPS-vs-EKF2 Pos &amp; GDI (7 features)</text>
    <text x="288" y="124" class="svg-box-sub">• GPS-vs-EKF2 Vel Residuals (4 features)</text>
    <text x="288" y="142" class="svg-box-sub">• GPS Kinematics &amp; OF Disp (5 features)</text>
    <text x="288" y="160" class="svg-box-sub">• IMU Integral dV Check (3 features)</text>
    <text x="288" y="178" class="svg-box-sub">• Gyro-Comp OF+LiDAR Vel (5 features)</text>

    <rect x="584" y="44" width="248" height="154" rx="6" fill="#FCFBF7" stroke="#18232E" stroke-width="1.3"/>
    <text x="596" y="66" class="svg-box-title">3. ML Scorer &amp; Gate</text>
    <text x="596" y="87" class="svg-box-sub">Model: RF (250) or XGBoost (250)</text>
    <text x="596" y="105" class="svg-box-sub">Vector x_t in R^24 -&gt; p = P(spoof)</text>
    <text x="596" y="125" class="svg-box-sub">Warmup Guard: settle_s &gt;= 2.5 s</text>
    <text x="596" y="143" class="svg-box-sub">Threshold: p &gt;= 0.80 (RF) / 0.82 (XGB)</text>
    <text x="596" y="161" class="svg-box-sub">Persistence: _consec_hits == 5</text>
    <text x="596" y="182" class="svg-box-sub" fill="#166B48">Prevents sharp-turn false triggers</text>

    <rect x="866" y="44" width="278" height="154" rx="6" fill="#EEF7F2" stroke="#166B48" stroke-width="1.6"/>
    <text x="878" y="66" class="svg-box-title" fill="#166B48">4. Atomic Failover (6.7-8.2 ms)</text>
    <text x="878" y="87" class="svg-box-sub">Step 1: Publish /guardian/failover_active</text>
    <text x="878" y="105" class="svg-box-sub">Step 2: DO_SET_MODE -&gt; AUTO.LOITER</text>
    <text x="878" y="125" class="svg-box-sub">Step 3: PARAM_SET (C-union INT32):</text>
    <text x="878" y="144" class="svg-mono">  EKF2_GPS_CTRL = 0   (cut GPS)</text>
    <text x="878" y="162" class="svg-mono">  EKF2_HGT_REF  = 2   (1D LiDAR)</text>
    <text x="878" y="180" class="svg-mono">  EKF2_OF_CTRL=1, EKF2_RNG_CTRL=2</text>

    <path d="M241,121 L275,121" stroke="#18232E" stroke-width="1.8" fill="none" marker-end="url(#lld-ink)"/>
    <path d="M550,121 L584,121" stroke="#18232E" stroke-width="1.8" fill="none" marker-end="url(#lld-ink)"/>
    <path d="M832,121 L866,121" stroke="#166B48" stroke-width="2.0" fill="none" marker-end="url(#lld-em)"/>

    <!-- Bottom Strip: State Machine & Bit-Packing Detail -->
    <text x="16" y="236" class="svg-zone-title">B. Guardian State Machine &amp; MAVLink Parameter Cutover Sequence</text>

    <rect x="16" y="254" width="225" height="162" rx="6" fill="#FCFBF7" stroke="#4F5D6B" stroke-width="1.2"/>
    <text x="28" y="277" class="svg-box-title">WARMUP / ARMED_CLIMB</text>
    <text x="28" y="298" class="svg-box-sub">Checks airborne height (-z &gt;= 1.5 m)</text>
    <text x="28" y="317" class="svg-box-sub">Waits 2.5 s for EKF2 climb settle</text>
    <text x="28" y="336" class="svg-box-sub">Fills circular buffer (len &gt;= 10)</text>
    <text x="28" y="355" class="svg-box-sub">Drains stale MAVLink RX packets</text>
    <text x="28" y="394" class="svg-box-sub" fill="#1B5299">guardian_monitoring = False</text>

    <rect x="304" y="254" width="246" height="162" rx="6" fill="#F4F7FB" stroke="#1B5299" stroke-width="1.4"/>
    <text x="316" y="277" class="svg-box-title" fill="#1B5299">NOMINAL_MONITORING</text>
    <text x="316" y="298" class="svg-box-sub">GPS + OF + LiDAR fused together</text>
    <text x="316" y="317" class="svg-box-sub">Scores features @ 20 Hz (50 ms tick)</text>
    <text x="316" y="336" class="svg-box-sub">If p &lt; 0.80: _consec_hits = 0</text>
    <text x="316" y="355" class="svg-box-sub">If p &gt;= 0.80: _consec_hits += 1</text>
    <text x="316" y="394" class="svg-box-sub" fill="#1B5299">cs_gps=True, mode=OFFBOARD</text>

    <rect x="614" y="254" width="246" height="162" rx="6" fill="#FAF0EE" stroke="#B43427" stroke-width="1.4"/>
    <text x="626" y="277" class="svg-box-title" fill="#B43427">SPOOF CONFIRMED (hits=5)</text>
    <text x="626" y="298" class="svg-box-sub">Sustained 0.25 s anomaly confirmed</text>
    <text x="626" y="317" class="svg-box-sub">encode_param_value(int32 -&gt; float32)</text>
    <text x="626" y="336" class="svg-box-sub">fast_cutover=True skips pre-read RTT</text>
    <text x="626" y="355" class="svg-box-sub">Verifies PARAM_VALUE echo match</text>
    <text x="626" y="394" class="svg-box-sub" fill="#B43427">Total cutover: 6.7 - 8.2 ms</text>

    <rect x="920" y="254" width="224" height="162" rx="6" fill="#EEF7F2" stroke="#166B48" stroke-width="1.6"/>
    <text x="932" y="277" class="svg-box-title" fill="#166B48">GPS_DENIED_HOLD_LOCK</text>
    <text x="932" y="298" class="svg-box-sub">cs_gps = False (0.0% in ULog tail)</text>
    <text x="932" y="317" class="svg-box-sub">cs_opt_flow = True, cs_rng_hgt = True</text>
    <text x="932" y="336" class="svg-box-sub">5 Hz watchdog holds AUTO.LOITER</text>
    <text x="932" y="355" class="svg-box-sub">Hover drift &lt;= 0.014 m/s (ULog)</text>
    <text x="932" y="394" class="svg-box-sub" fill="#166B48">Safe stabilization achieved</text>

    <path d="M241,335 L304,335" stroke="#18232E" stroke-width="1.8" fill="none" marker-end="url(#lld-ink)"/>
    <text x="249" y="324" class="svg-edge-label">settle ok</text>
    <path d="M550,335 L614,335" stroke="#B43427" stroke-width="1.8" fill="none" marker-end="url(#lld-car)"/>
    <text x="562" y="324" class="svg-edge-label" fill="#B43427">hits=5</text>
    <path d="M860,335 L920,335" stroke="#166B48" stroke-width="1.8" fill="none" marker-end="url(#lld-em)"/>
    <text x="869" y="324" class="svg-edge-label" fill="#166B48">cut ok</text>
  </svg>`;
}

export function renderControlPhysicsSvg() {
  return `
  <svg viewBox="0 0 1160 330" class="diagram-svg" role="img" aria-label="Closed-Loop Hijack vs Guardian Recovery Physics">
    <defs>
      <marker id="cp-ink" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,1 L7,4 L0,7 Z" fill="#18232E"/>
      </marker>
      <marker id="cp-car" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,1 L7,4 L0,7 Z" fill="#B43427"/>
      </marker>
      <marker id="cp-em" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,1 L7,4 L0,7 Z" fill="#166B48"/>
      </marker>
    </defs>

    <!-- Left Panel: Safe Nav OFF -->
    <rect x="14" y="14" width="550" height="302" rx="8" fill="#FCFBF7" stroke="#B43427" stroke-width="1.3"/>
    <text x="30" y="38" class="svg-box-title" fill="#B43427">Safe Navigation OFF: Closed-Loop Opposite Hijack Dynamics</text>

    <!-- Spatial corridor plot strictly within x=40..250 -->
    <rect x="64" y="64" width="150" height="145" fill="none" stroke="#9A6315" stroke-width="1.4" stroke-dasharray="5,4"/>
    <circle cx="64" cy="209" r="5" fill="#9A6315"/>
    <text x="142" y="226" class="svg-box-sub" fill="#9A6315">WP4 Bot-Left (-6,-6)</text>

    <!-- Real drone near mid-leg 4 -->
    <circle cx="142" cy="185" r="7" fill="#1B5299"/>
    <text x="155" y="191" class="svg-box-sub" fill="#1B5299">Real UAV</text>

    <!-- Spoofed GPS arrow North-East inside plot -->
    <path d="M142,185 L212,115" stroke="#B43427" stroke-width="2.4" fill="none" marker-end="url(#cp-car)"/>
    <circle cx="218" cy="109" r="6" fill="none" stroke="#B43427" stroke-width="2"/>
    <text x="150" y="96" class="svg-box-sub" fill="#B43427">Spoofed GPS (+N, +E bias)</text>

    <!-- Physical flight arrow South-West cleanly into bottom-left whitespace -->
    <path d="M137,190 L52,262" stroke="#18232E" stroke-width="2.4" stroke-dasharray="4,2" fill="none" marker-end="url(#cp-ink)"/>
    <text x="26" y="286" class="svg-box-sub" fill="#18232E">Physical hijack SW (-13.1, -13.0)</text>

    <!-- Explanatory text box strictly right of x=268, generous width=282 -->
    <rect x="268" y="116" width="282" height="180" rx="6" fill="#FAF0EE" stroke="#D8D0C1" stroke-width="1"/>
    <text x="282" y="140" class="svg-box-title">Why the UAV flies opposite the arrow:</text>
    <text x="282" y="164" class="svg-box-sub">1. Red arrow shows spoofed GPS shifted NE.</text>
    <text x="282" y="185" class="svg-box-sub">2. EKF2 believes UAV drifted NE of WP4.</text>
    <text x="282" y="206" class="svg-box-sub">3. Controller applies correction vector:</text>
    <text x="288" y="226" class="svg-mono" fill="#B43427">u_corr = p_target - (p_real + b_spoof)</text>
    <text x="282" y="250" class="svg-box-sub">4. Autopilot steers South-West (-b_spoof),</text>
    <text x="282" y="270" class="svg-box-sub">   pulling the drone 10.7 m off course.</text>

    <!-- Right Panel: Safe Nav ON -->
    <rect x="596" y="14" width="550" height="302" rx="8" fill="#FCFBF7" stroke="#166B48" stroke-width="1.3"/>
    <text x="612" y="38" class="svg-box-title" fill="#166B48">Safe Navigation ON: AI Spoof Isolation &amp; Optical Flow Hold</text>

    <!-- Spatial corridor plot strictly within x=632..825 -->
    <rect x="642" y="64" width="150" height="145" fill="none" stroke="#9A6315" stroke-width="1.4" stroke-dasharray="5,4"/>
    <circle cx="642" cy="209" r="5" fill="#9A6315"/>
    <text x="612" y="264" class="svg-box-sub" fill="#9A6315">WP4 Bot-Left (-6,-6)</text>

    <circle cx="718" cy="209" r="18" fill="#DDF3E6" stroke="#166B48" stroke-width="2.2"/>
    <circle cx="718" cy="209" r="6" fill="#166B48"/>
    <text x="655" y="244" class="svg-box-sub" fill="#166B48">HOLD LOCK (OF + LiDAR)</text>

    <!-- Ignored Spoofed GPS kept well inside plot x<=820 -->
    <path d="M718,209 L784,132" stroke="#B43427" stroke-width="2" stroke-dasharray="5,3" fill="none" marker-end="url(#cp-car)"/>
    <circle cx="789" cy="126" r="6" fill="none" stroke="#B43427" stroke-width="2"/>
    <text x="702" y="108" class="svg-box-sub" fill="#B43427">Ignored Spoofed GPS</text>

    <!-- Explanatory text box strictly right of x=848, generous width=284 -->
    <rect x="848" y="64" width="284" height="232" rx="6" fill="#EEF7F2" stroke="#D8D0C1" stroke-width="1"/>
    <text x="862" y="88" class="svg-box-title" fill="#166B48">AI Guardian Interception (6.7-8.2 ms):</text>
    <text x="862" y="114" class="svg-box-sub">1. Spoof arrives on Leg 4 toward WP4.</text>
    <text x="862" y="135" class="svg-box-sub">2. AI detects GPS-vs-OF conflict (P=0.989).</text>
    <text x="862" y="156" class="svg-box-sub">3. Sends AUTO.LOITER + EKF2_GPS_CTRL=0.</text>
    <text x="862" y="177" class="svg-box-sub">4. Promotes EKF2_HGT_REF=2 (1D LiDAR)</text>
    <text x="862" y="197" class="svg-box-sub">   and Optical Flow velocity fusion.</text>
    <text x="862" y="232" class="svg-box-sub">Result: Spoofed GPS diverges 10+ m while</text>
    <text x="862" y="253" class="svg-box-sub">real position holds within 0.12 m error.</text>
  </svg>`;
}

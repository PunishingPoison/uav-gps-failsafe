import {
  ABLATION_RUNS,
  CODE_MODULES,
  DATASET_EPISODES,
  DATASET_SOURCES,
  DATASET_SUMMARY,
  FEATURE_GROUPS,
  IEEE_REFERENCES,
  LITERATURE_MATRIX,
  MODEL_EVALUATION,
  MODERN_TOOLS,
  PROBLEM_AND_SCOPE,
  PROJECT_FLOW,
  PROJECT_META,
  RESEARCH_CATEGORIES,
} from "./data.js";
import {
  renderControlPhysicsSvg,
  renderHldDiagramSvg,
  renderLldDiagramSvg,
} from "./diagrams.js";

const TAB_ORDER = [
  { id: "overview", label: "Overview & Problem" },
  { id: "architecture", label: "Architecture (HLD & LLD)" },
  { id: "ai", label: "AI, Datasets & Code" },
  { id: "simulation", label: "Simulation & Results" },
  { id: "research", label: "Research & Literature" },
];

function esc(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function pagerHtml(currentId) {
  const idx = TAB_ORDER.findIndex((t) => t.id === currentId);
  const prev = idx > 0 ? TAB_ORDER[idx - 1] : null;
  const next = idx < TAB_ORDER.length - 1 ? TAB_ORDER[idx + 1] : null;
  return `
    <div class="section-pager">
      <button class="pager-btn" ${prev ? `data-jump="${prev.id}"` : "disabled"}>
        ${prev ? `Previous: ${esc(prev.label)}` : "Start of Dossier"}
      </button>
      <button class="pager-btn" ${next ? `data-jump="${next.id}"` : "disabled"}>
        ${next ? `Next: ${esc(next.label)}` : "End of Dossier"}
      </button>
    </div>
  `;
}

function renderOverview() {
  const metricsHtml = PROJECT_META.headlineMetrics
    .map(
      (m) => `
      <div class="metric-tile tone-${esc(m.tone)}">
        <div class="metric-label">${esc(m.label)}</div>
        <div class="metric-value">${esc(m.value)}</div>
        <div class="metric-detail">${esc(m.detail)}</div>
      </div>`
    )
    .join("");

  const flowHtml = PROJECT_FLOW.map(
    (step) => `
    <article class="flow-item">
      <div class="flow-head">
        <span class="flow-num">STAGE ${esc(step.step)}</span>
        <h4 class="flow-title">${esc(step.title)}</h4>
      </div>
      <p class="flow-detail">${esc(step.detail)}</p>
      <div class="flow-artifacts">${esc(step.artifacts)}</div>
    </article>`
  ).join("");

  const objHtml = PROBLEM_AND_SCOPE.objectives
    .map(
      (obj) => `
      <div class="obj-item">
        <div class="obj-tag">${esc(obj.id)}</div>
        <strong>${esc(obj.title)}</strong>
        <p class="prose" style="margin:4px 0 0;font-size:0.91rem;">${esc(obj.description)}</p>
      </div>`
    )
    .join("");

  const scopeHtml = PROBLEM_AND_SCOPE.scopeBounds
    .map((item) => `<li style="margin-bottom:8px;">${esc(item)}</li>`)
    .join("");

  return `
    <div class="hero-grid">
      <div>
        <div class="section-header" style="border-bottom:none;padding-bottom:0;margin-bottom:14px;">
          <h1>${esc(PROJECT_META.title)}</h1>
          <p class="section-lead">${esc(PROJECT_META.subtitle)}</p>
        </div>
        <div class="filter-bar" style="margin-top:18px;">
          <button class="filter-btn active" data-jump="simulation">View Safe Nav OFF vs. ON Results</button>
          <button class="filter-btn" data-jump="architecture">Inspect HLD &amp; LLD Diagrams</button>
          <button class="filter-btn" data-jump="ai">Explore AI &amp; Datasets</button>
        </div>
      </div>
      <figure class="paper-panel" style="margin:0;padding:14px;">
        <img src="assets/images/sim_safenav_on_gazebo.png" alt="PX4 x500 hovering inside AI Guardian green shield under GPS spoofing on Leg 4" class="figure-img" style="margin-top:0;">
        <figcaption>Live Gazebo Harmonic capture: Rogue Spoofer TX (-8, +8) beams false GPS toward the quadrotor on Leg 4; AI Guardian isolates GPS and locks Optical Flow + 1D LiDAR hover (emerald ring).</figcaption>
      </figure>
    </div>

    <div class="hero-metrics">${metricsHtml}</div>

    <h3 class="subhead">1. Introduction &amp; Problem Statement</h3>
    <div class="two-col">
      <div class="paper-panel">
        <h4 style="margin-top:0;">Introduction &amp; Core Idea</h4>
        <p class="prose">${esc(PROBLEM_AND_SCOPE.introduction)}</p>
        <p class="prose" style="margin-bottom:0;">To solve this without expensive cryptographic receivers or heavy visual-SLAM payloads, the companion stack continually compares GPS kinematics against physically tamper-resistant onboard sensors (IMU specific force, gyro-compensated downward Lucas-Kanade optical flow, and 1D LiDAR rangefinding) and executes automated PX4 EKF2 isolation on sustained spoofing.</p>
      </div>
      <div class="inset-panel">
        <h4 style="margin-top:0;color:var(--carmine);">Problem Statement</h4>
        <p class="prose" style="margin-bottom:0;">${esc(PROBLEM_AND_SCOPE.problemStatement)}</p>
      </div>
    </div>

    <h3 class="subhead">2. Project Flow — End-to-End Lifecycle</h3>
    <div class="flow-list">${flowHtml}</div>

    <h3 class="subhead">3. Bounded Objectives &amp; Project Scope</h3>
    <div class="two-col">
      <div class="paper-panel">
        <h4 style="margin-top:0;">Project Objectives</h4>
        ${objHtml}
      </div>
      <div class="paper-panel">
        <h4 style="margin-top:0;">Defined Engineering Scope</h4>
        <ul style="margin:0;padding-left:18px;font-size:0.92rem;">${scopeHtml}</ul>
      </div>
    </div>
    ${pagerHtml("overview")}
  `;
}

function renderArchitecture() {
  return `
    <div class="section-header">
      <h2>System Architecture — High-Level &amp; Low-Level Design</h2>
      <p class="section-lead">Complete architectural blueprint spanning the Gazebo Harmonic physics simulator, MAVLink/uXRCE-DDS transport buses, 20 Hz causal feature pipeline, and PX4 EKF2 recovery state machine.</p>
    </div>

    <h3 class="subhead" style="margin-top:0;">1. High-Level Design (HLD) — Modular System Architecture</h3>
    <p class="prose">The testbed cleanly decouples Gazebo sensor generation, adversarial HIL_GPS preemption, PX4 EKF2 estimation, and companion ML supervision inside a single containerized ROS 2 Jazzy + PX4 v1.15.4 runtime.</p>
    <div class="diagram-frame">${renderHldDiagramSvg()}</div>

    <h3 class="subhead">2. Low-Level Design (LLD) — 20 Hz Feature Pipeline &amp; Failover State Machine</h3>
    <p class="prose">To guarantee zero train/serve skew, <code>guardian_ai_node</code> runs the exact same <code>FeatureWindowExtractor</code> Python class used to generate offline training matrices. A 5-tick persistence gate (<code>0.25 s</code> at <code>20 Hz</code>) prevents false alarms during aggressive waypoint reversals while triggering atomic C-union <code>INT32</code> parameter overrides in <code>6.7–8.2 ms</code>.</p>
    <div class="diagram-frame">${renderLldDiagramSvg()}</div>

    <h3 class="subhead">3. Closed-Loop Control Physics — Why Unprotected Drones Steer Opposite the Spoof Arrow</h3>
    <p class="prose">In Stage 1 (Safe Navigation OFF), the red tactical vector points from the quadrotor's physical position toward the spoofed GPS coordinate. Understanding why the aircraft moves in the opposite direction is key to proving real closed-loop EKF2 hijacking:</p>
    <div class="diagram-frame">${renderControlPhysicsSvg()}</div>

    <h3 class="subhead">4. Custom Quadrotor Model, Airframe 4015 &amp; World Configuration</h3>
    <div class="two-col">
      <div class="paper-panel">
        <h4 style="margin-top:0;">Sensor Suite (x500_flow_lidar/model.sdf)</h4>
        <ul style="margin:0;padding-left:18px;font-size:0.90rem;">
          <li><strong>Downward Flow Camera:</strong> 128&times;128 RGB, <code>0.80 rad</code> HFOV, 30 Hz (<code>/gz/downward_camera/image</code>), processed via OpenCV Lucas-Kanade pyramids (<code>winSize=(15,15)</code>, <code>maxLevel=2</code>).</li>
          <li><strong>Downward 1D LiDAR:</strong> 1&times;1 <code>gpu_lidar</code>, <code>0.05–60.0 m</code> range, <code>0.01 m</code> Gaussian noise @ 30 Hz (<code>/gz/downward_lidar/scan</code>).</li>
          <li><strong>HIL_GPS Spoofable Receiver:</strong> Nominal <code>sensor_bridge_node</code> transmits on UDP <code>14030</code>; <code>adversary_spoofer_node</code> preempts via <code>/adversary/active</code> on UDP <code>13030</code>.</li>
          <li><strong>Ground-Truth Odometry:</strong> 50 Hz <code>OdometryPublisher</code> (<code>/gz/ground_truth/odom</code>) used strictly for evaluation and logging—never read by AI models.</li>
        </ul>
      </div>
      <div class="paper-panel">
        <h4 style="margin-top:0;">PX4 Airframe 4015 &amp; EKF2 Transition Matrix</h4>
        <div class="table-wrap" style="margin-bottom:0;">
          <table>
            <thead><tr><th>Parameter</th><th>Nominal Mode</th><th>Failover (GPS-Denied)</th></tr></thead>
            <tbody>
              <tr><td class="mono">SENS_EN_GPSSIM</td><td class="mono">0 (HIL_GPS active)</td><td class="mono">0</td></tr>
              <tr><td class="mono">EKF2_GPS_CTRL</td><td class="mono">7 (Pos+Vel+Alt GPS)</td><td class="mono" style="color:var(--emerald);font-weight:700;">0 (GPS Isolated)</td></tr>
              <tr><td class="mono">EKF2_OF_CTRL</td><td class="mono">1 (Enabled)</td><td class="mono" style="color:var(--emerald);font-weight:700;">1 (Primary Horizontal)</td></tr>
              <tr><td class="mono">EKF2_RNG_CTRL</td><td class="mono">2 (Unconditional)</td><td class="mono" style="color:var(--emerald);font-weight:700;">2 (Active Range Aid)</td></tr>
              <tr><td class="mono">EKF2_HGT_REF</td><td class="mono">1 (GPS Height Ref)</td><td class="mono" style="color:var(--emerald);font-weight:700;">2 (1D LiDAR Height)</td></tr>
              <tr><td class="mono">Flight Mode</td><td class="mono">OFFBOARD</td><td class="mono" style="color:var(--emerald);font-weight:700;">AUTO.LOITER (Hold)</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
    ${pagerHtml("architecture")}
  `;
}

function renderAiAndCode() {
  const episodeRows = DATASET_EPISODES.map(
    (e) => `
    <tr>
      <td class="mono">${esc(e.id)}</td>
      <td><span class="badge ${e.split === "test" ? "badge-amber" : "badge-cobalt"}">${esc(e.split)}</span></td>
      <td><span class="badge ${e.mode === "none" ? "badge-emerald" : "badge-carmine"}">${esc(e.mode)}</span></td>
      <td>${esc(e.pattern)}</td>
      <td class="mono">${esc(e.speed)}</td>
      <td>${esc(e.params)}</td>
      <td class="mono">${esc(e.lines)}</td>
      <td style="white-space:nowrap;">
        <button type="button" class="lb-btn" data-load-csv="assets/data/raw/${esc(e.id)}.csv" data-load-label="raw / ${esc(e.id)}.csv">Browse Rows</button>
        <a class="lb-btn" href="assets/data/raw/${esc(e.id)}.csv" download style="text-decoration:none;">CSV</a>
      </td>
    </tr>`
  ).join("");

  const expDatasetRows = ABLATION_RUNS.map(
    (r) => `
    <tr>
      <td class="mono">${esc(r.runId)}.csv</td>
      <td>${esc(r.mode)}</td>
      <td><span class="badge ${r.guardian ? "badge-emerald" : "badge-carmine"}">${r.guardian ? "ON" : "OFF"}</span></td>
      <td class="mono">${esc(r.hijackRmse)}</td>
      <td class="mono">${esc(r.maxErr)}</td>
      <td style="white-space:nowrap;">
        <button type="button" class="lb-btn" data-load-csv="assets/data/experiments/${esc(r.runId)}.csv" data-load-label="experiments / ${esc(r.runId)}.csv">Browse Rows</button>
        <a class="lb-btn" href="assets/data/experiments/${esc(r.runId)}.csv" download style="text-decoration:none;">CSV</a>
      </td>
    </tr>`
  ).join("");

  const sourceOptions = [
    ...DATASET_SOURCES.map((s) => `<option value="${esc(s.url)}">${esc(s.group)}: ${esc(s.label)}</option>`),
    ...DATASET_EPISODES.map((e) => `<option value="assets/data/raw/${esc(e.id)}.csv">Raw Episode: ${esc(e.id)}.csv (${e.lines} lines x 76 cols)</option>`),
    ...ABLATION_RUNS.map((r) => `<option value="assets/data/experiments/${esc(r.runId)}.csv">Ablation Flight: ${esc(r.runId)}.csv</option>`),
  ].join("");

  const featureGroupsHtml = FEATURE_GROUPS.map(
    (grp) => `
    <div class="group-block">
      <h4>${esc(grp.group)}</h4>
      <p style="margin:0;font-size:0.87rem;color:var(--ink-muted);">${esc(grp.rationale)}</p>
      <div class="feature-grid">
        ${grp.features
          .map(
            (f) => `
          <div class="feature-item">
            <code>${esc(f.name)}</code>
            <div style="color:var(--ink-muted);margin-top:2px;">${esc(f.desc)}</div>
          </div>`
          )
          .join("")}
      </div>
    </div>`
  ).join("");

  const modelRows = MODEL_EVALUATION.models
    .map(
      (m) => `
    <tr>
      <td><strong>${esc(m.name)}</strong><div style="font-size:0.79rem;color:var(--ink-muted);">${esc(m.role)}</div></td>
      <td class="mono">${esc(m.threshold)}</td>
      <td class="mono">${esc(m.accuracy)}</td>
      <td class="mono">${esc(m.precision)}</td>
      <td class="mono">${esc(m.recall)}</td>
      <td class="mono"><strong>${esc(m.f1)}</strong></td>
      <td class="mono"><strong>${esc(m.rocAuc)}</strong></td>
      <td class="mono">${esc(m.nominalFpr)}</td>
      <td class="mono">${esc(m.stepRecall)} / ${esc(m.driftRecall)} / ${esc(m.takeoverRecall)}</td>
    </tr>`
    )
    .join("");

  const codeBlocks = CODE_MODULES.map(
    (mod) => `
    <div class="paper-panel">
      <h4 style="margin-top:0;color:var(--cobalt);">${esc(mod.layer)}</h4>
      <div class="table-wrap" style="margin-bottom:0;">
        <table>
          <thead><tr><th>File</th><th>Responsibility &amp; Implementation Scope</th></tr></thead>
          <tbody>
            ${mod.files
              .map((f) => `<tr><td class="mono" style="width:260px;">${esc(f.path)}</td><td>${esc(f.role)}</td></tr>`)
              .join("")}
          </tbody>
        </table>
      </div>
    </div>`
  ).join("");

  const toolsRows = MODERN_TOOLS.map(
    (t) => `
    <tr>
      <td><strong>${esc(t.tool)}</strong></td>
      <td><span class="badge badge-cobalt">${esc(t.category)}</span></td>
      <td>${esc(t.justification)}</td>
    </tr>`
  ).join("");

  return `
    <div class="section-header">
      <h2>AI Pipeline, Telemetry Datasets &amp; Codebase</h2>
      <p class="section-lead">Complete training provenance: 16 raw SITL flight episodes (7,621 sliding windows &times; 24 causal features), Random Forest &amp; XGBoost evaluation on held-out episodes, and full module/tool inventory.</p>
    </div>

    <div class="filter-bar" role="tablist" aria-label="AI sub-sections">
      <button class="filter-btn active" data-subview="sub-dataset">1. Dataset Collection (16 Episodes)</button>
      <button class="filter-btn" data-subview="sub-features">2. 24 Engineered Features</button>
      <button class="filter-btn" data-subview="sub-models">3. Models (RF, XGBoost &amp; Baseline)</button>
      <button class="filter-btn" data-subview="sub-code">4. Code Modules &amp; Modern Tools</button>
    </div>

    <div id="sub-dataset" class="subview">
      <div class="inset-panel">
        <strong>Dataset Collection Protocol (<code>ml/collect_dataset.py</code>):</strong>
        Each episode boots an isolated headless PX4 + Gazebo instance, records <strong>76 raw telemetry columns at 20 Hz</strong> via <code>telemetry_logger_node</code>, and writes <code>data/raw/dataset_manifest.json</code>. Strict <strong>episode-level train/test splitting</strong> isolates the 12 training episodes (<strong>${DATASET_SUMMARY.trainRows}</strong> airborne windows) from 4 held-out test episodes (<strong>${DATASET_SUMMARY.testRows}</strong> airborne windows). Every row of the processed dataset (<strong>${DATASET_SUMMARY.totalFeatureWindows} windows &times; 42 columns</strong>), all <strong>16 raw CSVs</strong>, and all <strong>10 ablation CSVs</strong> can be inspected or downloaded below.
      </div>

      <h3 class="subhead" style="margin-top:0;">Interactive Full-Dataset Browser (All Rows &amp; Columns)</h3>
      <div class="ds-toolbar">
        <div class="ds-field" style="grid-column: span 2;">
          <label for="ds-source-select">Active Dataset CSV</label>
          <select id="ds-source-select" class="ds-select">${sourceOptions}</select>
        </div>
        <div class="ds-field">
          <label for="ds-episode-filter">Filter by Episode</label>
          <select id="ds-episode-filter" class="ds-select"><option value="all">All Episodes</option></select>
        </div>
        <div class="ds-field">
          <label for="ds-label-filter">Filter by Spoof Label</label>
          <select id="ds-label-filter" class="ds-select">
            <option value="all">All Rows (Nominal + Spoofed)</option>
            <option value="0">Nominal Only (spoof_active = 0)</option>
            <option value="1">Spoofed Only (spoof_active = 1)</option>
          </select>
        </div>
        <div class="ds-field" style="grid-column: span 2;">
          <label for="ds-search-input">Search Any Value (mode, phase, episode, etc.)</label>
          <input id="ds-search-input" class="ds-input" type="search" placeholder="Type to filter rows (e.g. drift, takeover, OFFBOARD)...">
        </div>
        <div class="ds-field">
          <label for="ds-page-size">Rows Per Page</label>
          <select id="ds-page-size" class="ds-select">
            <option value="25">25 rows / page</option>
            <option value="50" selected>50 rows / page</option>
            <option value="100">100 rows / page</option>
            <option value="250">250 rows / page</option>
          </select>
        </div>
        <div class="ds-field" style="justify-content:flex-end;">
          <label>Actions</label>
          <div style="display:flex;gap:8px;">
            <button type="button" id="ds-toggle-schema" class="lb-btn" style="flex:1;">Columns Schema</button>
            <a id="ds-download-link" class="lb-btn" href="assets/data/processed/features_dataset.csv" download style="text-decoration:none;text-align:center;flex:1;">Download CSV</a>
          </div>
        </div>
      </div>

      <div id="ds-schema-box" class="ds-schema-box" style="display:none;"></div>

      <div class="ds-meta-bar">
        <span id="ds-stats-text">Loading full dataset CSV...</span>
        <span id="ds-split-pills"></span>
      </div>

      <div class="ds-scroll-wrap">
        <table id="ds-table">
          <thead id="ds-thead"></thead>
          <tbody id="ds-tbody"><tr><td style="padding:16px;">Loading dataset rows...</td></tr></tbody>
        </table>
      </div>

      <div class="ds-pager">
        <div style="display:flex;gap:8px;align-items:center;">
          <button type="button" id="ds-prev-page" class="pager-btn" style="padding:6px 12px;">Previous Page</button>
          <span id="ds-page-info" class="mono">Page 1 / 1</span>
          <button type="button" id="ds-next-page" class="pager-btn" style="padding:6px 12px;">Next Page</button>
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
          <span style="font-size:0.82rem;color:var(--ink-muted);">Manifests:</span>
          <a class="lb-btn" href="assets/data/raw/dataset_manifest.json" target="_blank" rel="noopener noreferrer" style="text-decoration:none;">dataset_manifest.json</a>
          <a class="lb-btn" href="assets/data/experiments/experiments_manifest.json" target="_blank" rel="noopener noreferrer" style="text-decoration:none;">experiments_manifest.json</a>
        </div>
      </div>

      <h3 class="subhead">16 Raw SITL Collection Episodes (data/raw/*.csv — 76 Columns @ 20 Hz)</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>Episode ID</th><th>Split</th><th>Attack Mode</th><th>Flight Pattern</th><th>Speed</th><th>Parameters</th><th>CSV Lines</th><th>Inspect / Download</th></tr>
          </thead>
          <tbody>${episodeRows}</tbody>
        </table>
      </div>

      <h3 class="subhead">10 Paired Ablation Experiment CSVs (data/experiments/*.csv — 76 Columns)</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>CSV File</th><th>Scenario</th><th>Guardian</th><th>Hijack RMSE</th><th>Peak Err</th><th>Inspect / Download</th></tr>
          </thead>
          <tbody>${expDatasetRows}</tbody>
        </table>
      </div>
    </div>

    <div id="sub-features" class="subview" style="display:none;">
      <p class="prose">All 24 features live in <code>FEATURE_NAMES</code> inside <code>feature_extractor.py</code> and operate causally over a 20-sample (1.0 s) deque buffer using only onboard observables. Optical Flow angular rates are gyro-compensated and scaled by downward LiDAR range using <code>rx = -flow_x/dt + gyro_x</code>, <code>ry = +flow_y/dt - gyro_y</code> (verified against ground truth at <code>R &gt; 0.99</code>, <code>RMSE = 0.24 m/s</code>).</p>
      ${featureGroupsHtml}
    </div>

    <div id="sub-models" class="subview" style="display:none;">
      <p class="prose">Models were cross-validated across training episodes using 4-fold <code>StratifiedGroupKFold</code> (thresholds tuned for low nominal false positive rate), then evaluated once on the 4 completely unseen test episodes (<code>ep_nom_04_square_fast</code>, <code>ep_step_04_3p8m_e</code>, <code>ep_drift_04_1p2mps_nw</code>, <code>ep_take_04_1p6mps_se</code>). Online <code>guardian_ai_node</code> defaults to Random Forest at conservative threshold <code>0.80</code> across 5 consecutive ticks.</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>Model &amp; Hyperparameters</th><th>Threshold</th><th>Acc</th><th>Prec</th><th>Rec</th><th>F1</th><th>ROC-AUC</th><th>Nom FPR</th><th>Step / Drift / Take Recall</th></tr>
          </thead>
          <tbody>${modelRows}</tbody>
        </table>
      </div>
      <div class="inset-panel">
        <strong>CV &amp; Unseen Detection Latency Summary:</strong>
        <ul>
          <li><strong>Random Forest (<code>rf_detector.joblib</code>):</strong> 4-Fold OOF AUC <code>0.97721</code>, F1 <code>0.96573</code>, FPR <code>0.00089</code>. Unseen test detection latency: Step <code>0.2 s</code>, Drift <code>0.3 s</code>, Takeover <code>0.4 s</code>.</li>
          <li><strong>XGBoost (<code>xgb_detector.joblib</code>):</strong> Highest unseen ROC-AUC (<code>0.9885</code>), 4-Fold OOF AUC <code>0.97965</code>, F1 <code>0.95146</code>, FPR <code>0.00238</code>. Unseen latency: Step <code>0.3 s</code>, Drift <code>0.4 s</code>, Takeover <code>0.5 s</code>.</li>
          <li><strong>Threshold Baseline (<code>baseline_threshold.joblib</code>):</strong> Misses subtler step jumps (Step recall <code>0.6850</code> vs. <code>0.8583</code> for RF/XGBoost) and lacks multi-sensor cross-validation during fast maneuvers.</li>
        </ul>
      </div>
      <div class="figure-grid">
        <figure class="figure-card">
          <img src="assets/images/eval_roc_pr_curves.png" alt="ROC and Precision-Recall curves on unseen test flights" class="figure-img" style="margin-top:0;">
          <figcaption>ROC (XGBoost AUC=0.9885, RF AUC=0.9879) and Precision-Recall (RF AP=0.9872) on the 4 unseen test flights.</figcaption>
        </figure>
        <figure class="figure-card">
          <img src="assets/images/eval_feature_importance.png" alt="Random Forest and XGBoost feature importances" class="figure-img" style="margin-top:0;">
          <figcaption>Feature importances: windowed position residuals, GPS jumps, velocity residuals, and Optical Flow displacement errors dominate detection.</figcaption>
        </figure>
        <figure class="figure-card full-span">
          <img src="assets/images/eval_confusion_matrices.png" alt="Confusion matrices across Threshold Baseline, Random Forest, and XGBoost" class="figure-img" style="margin-top:0;">
          <figcaption>Confusion matrices on 1,927 unseen test windows showing Random Forest cutting missed spoofed frames from 15.4% (Threshold Baseline) down to 7.0%.</figcaption>
        </figure>
      </div>
    </div>

    <div id="sub-code" class="subview" style="display:none;">
      <h3 class="subhead" style="margin-top:0;">Repository Code Structure (<a href="${esc(PROJECT_META.repoUrl)}" target="_blank" rel="noopener noreferrer">GitHub</a>)</h3>
      ${codeBlocks}
      <h3 class="subhead">Modern Tools Identification &amp; Justification (CO4)</h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Tool / Framework</th><th>Role</th><th>Engineering Justification</th></tr></thead>
          <tbody>${toolsRows}</tbody>
        </table>
      </div>
      <div class="code-block"># Reproducible reproduction commands from README.md:
./scripts/check_env.sh
python3 ml/collect_dataset.py
python3 ml/train_models.py &amp;&amp; python3 ml/evaluate_models.py
python3 analysis/run_experiments.py &amp;&amp; python3 analysis/evaluate_experiments.py
./scripts/run_demo.sh   # Launches sequential Safe Nav OFF -&gt; Safe Nav ON live Gazebo + Tactical HUD</div>
    </div>
    ${pagerHtml("ai")}
  `;
}

function renderSimulation() {
  const ablationRows = ABLATION_RUNS.map(
    (r) => `
    <tr>
      <td class="mono">${esc(r.runId)}</td>
      <td>${esc(r.mode)}</td>
      <td><span class="badge ${r.guardian ? "badge-emerald" : "badge-carmine"}">${r.guardian ? "ON" : "OFF"}</span></td>
      <td class="mono">${esc(r.preRmse)}</td>
      <td class="mono">${esc(r.falseFailover)}</td>
      <td class="mono">${esc(r.latencyMs)}</td>
      <td class="mono" style="font-weight:700;color:${r.guardian ? "var(--emerald)" : "var(--carmine)"};">${esc(r.hijackRmse)}</td>
      <td class="mono">${esc(r.maxErr)}</td>
      <td class="mono">${esc(r.hoverDrift)}</td>
      <td class="mono">${esc(r.tailGpsPct)}</td>
    </tr>`
  ).join("");

  return `
    <div class="section-header">
      <h2>Live Simulation Showcase &amp; Ablation Verification</h2>
      <p class="section-lead">Sequential two-stage demonstration (<code>./scripts/run_demo.sh</code>): the drone executes Top-Left &rarr; Top-Right &rarr; Bottom-Right nominally, is attacked from Rogue TX <code>(-8, +8)</code> while flying to Bottom-Left, and compares Safe Navigation OFF vs. Safe Navigation ON.</p>
    </div>

    <div class="compare-grid">
      <div class="stage-card">
        <span class="badge badge-carmine">STAGE 1 / 2 · SAFE NAVIGATION OFF (UNPROTECTED)</span>
        <h3 style="margin:10px 0 6px;font-family:var(--font-display);">Trajectory Hijacked Off Corridor</h3>
        <p style="font-size:0.90rem;margin:0 0 12px;color:var(--ink-muted);">At T+46.2 s on Leg 4, Drift spoofing (<code>2.0 m/s @ 45 deg</code>) shifts the red Spoofed GPS phantom North-East. PX4's unguarded EKF2 steers South-West to compensate, pulling the real drone out to <code>(-13.1, -13.0)</code> (<strong>10.73 m</strong> error).</p>
        <img src="assets/images/sim_safenav_off_gazebo.png" alt="Gazebo 3D view with Safe Navigation OFF showing drone dragged off Leg 4" class="figure-img">
        <img src="assets/images/sim_safenav_off_hud.png" alt="Tactical HUD Stage 1 Safe Nav OFF" class="figure-img">
      </div>

      <div class="stage-card safe-on">
        <span class="badge badge-emerald">STAGE 2 / 2 · SAFE NAVIGATION ON (AI GUARDIAN)</span>
        <h3 style="margin:10px 0 6px;font-family:var(--font-display);">Spoof Isolated in 8.2 ms &amp; Hover Locked</h3>
        <p style="font-size:0.90rem;margin:0 0 12px;color:var(--ink-muted);">At T+43.7 s on Leg 4, the identical attack begins. AI Guardian detects divergence at T+44.2 s (<code>P = 0.975</code>), cuts <code>EKF2_GPS_CTRL=0</code> in <strong>8.2 ms</strong>, and locks Optical Flow + 1D LiDAR hover (<code>HijackErr = 0.09 m</code> vs. <code>GPS Res = 8.44 m</code>).</p>
        <img src="assets/images/sim_safenav_on_gazebo.png" alt="Gazebo 3D view with Safe Navigation ON showing emerald hover shield" class="figure-img">
        <img src="assets/images/sim_safenav_on_hud.png" alt="Tactical HUD Stage 2 Safe Nav ON" class="figure-img">
      </div>
    </div>

    <h3 class="subhead">10-Run Paired Ablation Results (CSV + PX4 Binary .ulg Logs)</h3>
    <p class="prose">Measured by <code>analysis/evaluate_experiments.py</code> across all 10 paired flights. Every guarded run achieved <strong>0.0% GPS fusion</strong> in post-failover PX4 <code>.ulg</code> tail logs, <strong>zero false failovers</strong> on fast 2.5 m/s nominal flight, and <strong>zero crashes</strong>.</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Run ID</th><th>Scenario</th><th>Guardian</th><th>Pre RMSE</th><th>False Trig</th><th>Det Latency</th><th>Hijack RMSE</th><th>Peak Err</th><th>Hover Drift</th><th>ULog Tail GPS</th></tr>
        </thead>
        <tbody>${ablationRows}</tbody>
      </table>
    </div>

    <h3 class="subhead">Publication Figures (300-DPI Experiment Plots)</h3>
    <div class="figure-grid">
      <figure class="figure-card full-span">
        <img src="assets/images/fig1_trajectory_comparison.png" alt="Spatial trajectory comparison across Step, Drift, and Takeover attacks" class="figure-img" style="margin-top:0;">
        <figcaption>Figure 1: Spatial trajectories (North vs. East) comparing unguarded spoofing excursion (red) against AI Guardian cutover &amp; hover lock (blue/green star).</figcaption>
      </figure>
      <figure class="figure-card">
        <img src="assets/images/fig2_recovery_timeseries.png" alt="Real-time spoofing interception and EKF2 flag switch timeseries" class="figure-img" style="margin-top:0;">
        <figcaption>Figure 2: Time-series showing instantaneous GPS isolation (<code>cs_gps</code> dropping 1 &rarr; 0) while Optical Flow and 1D LiDAR remain locked.</figcaption>
      </figure>
      <figure class="figure-card">
        <img src="assets/images/fig3_ablation_metrics.png" alt="Peak localization excursion and detection latency bar charts" class="figure-img" style="margin-top:0;">
        <figcaption>Figure 3: Peak localization excursion reduction (21.3 m &rarr; 0.19 m under Takeover) alongside detection latency (300–600 ms) and settled hover drift (&le; 1.4 cm/s).</figcaption>
      </figure>
    </div>
    ${pagerHtml("simulation")}
  `;
}

function renderResearch() {
  const matrixRows = LITERATURE_MATRIX.map(
    (row, idx) => `
    <tr>
      <td class="mono">${idx + 1}</td>
      <td><a href="${esc(row.url)}" target="_blank" rel="noopener noreferrer"><strong>${esc(row.citation)}</strong></a></td>
      <td>${esc(row.methodology)}</td>
      <td>${esc(row.findings)}</td>
      <td>${esc(row.results)}</td>
      <td>${esc(row.limitations)}</td>
    </tr>`
  ).join("");

  const catButtons = [
    `<button class="filter-btn active" data-cat-filter="all">All 7 Themes (41 Links)</button>`,
    ...RESEARCH_CATEGORIES.map(
      (c, i) => `<button class="filter-btn" data-cat-filter="cat-${i}">${esc(c.category.replace(/^\d+\.\s*/, ""))}</button>`
    ),
  ].join("");

  const categoriesHtml = RESEARCH_CATEGORIES.map(
    (cat, i) => `
    <div class="paper-panel research-cat-block" data-cat-id="cat-${i}">
      <h4 style="margin-top:0;color:var(--cobalt);">${esc(cat.category)}</h4>
      <p style="margin:0 0 12px;font-size:0.89rem;color:var(--ink-muted);">${esc(cat.summary)}</p>
      <ul class="paper-list">
        ${cat.papers
          .map(
            (p) => `
          <li class="paper-row">
            <div>
              <a href="${esc(p.url)}" target="_blank" rel="noopener noreferrer" style="font-weight:600;">${esc(p.title)}</a>
              <div class="paper-meta">${esc(p.role)}</div>
            </div>
            <a class="badge badge-cobalt" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;flex-shrink:0;">Open Source</a>
          </li>`
          )
          .join("")}
      </ul>
    </div>`
  ).join("");

  const ieeeHtml = IEEE_REFERENCES.map((r) => `<li style="margin-bottom:8px;font-size:0.90rem;">${esc(r)}</li>`).join("");

  return `
    <div class="section-header">
      <h2>Research Survey &amp; Literature Library</h2>
      <p class="section-lead">Peer-reviewed literature synthesis sorted from <strong>Latest to Oldest (2026 &rarr; 2018)</strong>, plus the complete 7-theme repository of all 41 source papers studied for this architecture.</p>
    </div>

    <h3 class="subhead" style="margin-top:0;">1. Structured Literature Review Matrix (Sorted Latest to Oldest)</h3>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>#</th><th>Author / Title / Year</th><th>Applied Methodology / Algorithm Used</th><th>Findings</th><th>Results</th><th>Limitations</th></tr>
        </thead>
        <tbody>${matrixRows}</tbody>
      </table>
    </div>

    <h3 class="subhead">2. Complete Categorized Research Repository (41 Papers across 7 Themes)</h3>
    <div class="filter-bar">${catButtons}</div>
    <div id="research-categories-wrap">${categoriesHtml}</div>

    <h3 class="subhead">3. References (IEEE Format)</h3>
    <div class="paper-panel">
      <ol style="margin:0;padding-left:20px;list-style:none;">${ieeeHtml}</ol>
    </div>
    ${pagerHtml("research")}
  `;
}

const RENDERERS = {
  overview: renderOverview,
  architecture: renderArchitecture,
  ai: renderAiAndCode,
  simulation: renderSimulation,
  research: renderResearch,
};

function enhanceZoomableMedia() {
  document.querySelectorAll(".diagram-frame").forEach((frame) => {
    const svg = frame.querySelector("svg.diagram-svg");
    if (!svg || frame.querySelector(".zoom-trigger-bar")) return;
    const title = svg.getAttribute("aria-label") || "Architecture Diagram";
    const bar = document.createElement("div");
    bar.className = "zoom-trigger-bar";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "zoom-open-btn";
    btn.textContent = "Expand & Zoom";
    btn.addEventListener("click", () => openLightboxWithSvg(svg, title, ""));
    bar.appendChild(btn);
    frame.prepend(bar);
    svg.addEventListener("click", () => openLightboxWithSvg(svg, title, ""));
  });

  document.querySelectorAll("img.figure-img").forEach((img) => {
    img.title = "Click to enlarge and zoom";
    img.addEventListener("click", () => {
      const fig = img.closest("figure");
      const card = img.closest(".stage-card");
      const capEl = fig ? fig.querySelector("figcaption") : null;
      const capText = capEl ? capEl.textContent : img.alt || "";
      let titleText = img.alt || "Figure Viewer";
      if (card) {
        const badge = card.querySelector(".badge");
        if (badge) titleText = `${badge.textContent} — ${img.alt}`;
      }
      openLightboxWithImg(img.src, titleText, capText);
    });
  });

  // Add subtle Expand & Zoom buttons inside simulation/figure cards too
  document.querySelectorAll(".figure-card, .stage-card").forEach((card) => {
    if (card.querySelector(".zoom-trigger-bar")) return;
    const imgs = card.querySelectorAll("img.figure-img");
    if (!imgs.length) return;
    const targetImg = imgs[0];
    const bar = document.createElement("div");
    bar.className = "zoom-trigger-bar";
    bar.style.marginTop = "8px";
    bar.style.marginBottom = "0";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "zoom-open-btn";
    btn.textContent = imgs.length > 1 ? "Expand Screenshots to Zoom" : "Expand & Zoom";
    btn.addEventListener("click", () => targetImg.click());
    bar.appendChild(btn);
    card.insertBefore(bar, targetImg);
  });
}

function mountAllPanels() {
  for (const { id } of TAB_ORDER) {
    const panel = document.getElementById(`panel-${id}`);
    if (panel) {
      panel.innerHTML = RENDERERS[id]();
    }
  }
  enhanceZoomableMedia();
}

const TAB_ALIASES = {
  results: "simulation",
  literature: "research",
  hld: "architecture",
  lld: "architecture",
  datasets: "ai",
  code: "ai",
};

function resolveTabId(rawId) {
  const mapped = TAB_ALIASES[rawId] || rawId;
  return TAB_ORDER.some((t) => t.id === mapped) ? mapped : "overview";
}

function activateTab(tabId, pushHash = true) {
  const valid = resolveTabId(tabId);
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.setAttribute("aria-selected", btn.dataset.tab === valid ? "true" : "false");
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `panel-${valid}`);
  });
  if (pushHash && window.location.hash !== `#${valid}`) {
    history.replaceState(null, "", `#${valid}`);
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// --- Lightbox Zoom & Pan Controller ---
const lbState = { zoom: 1.0, tx: 0, ty: 0, dragging: false, startX: 0, startY: 0, startTx: 0, startTy: 0 };

function applyLbTransform() {
  const canvas = document.getElementById("lightbox-canvas");
  const readout = document.getElementById("lightbox-zoom-readout") || document.getElementById("lb-zoom-readout");
  if (canvas) {
    canvas.style.transform = `translate(${lbState.tx}px, ${lbState.ty}px) scale(${lbState.zoom})`;
  }
  if (readout) {
    readout.textContent = `${Math.round(lbState.zoom * 100)}%`;
  }
}

function resetLbView() {
  lbState.zoom = 1.0;
  lbState.tx = 0;
  lbState.ty = 0;
  applyLbTransform();
}

function stepLbZoom(delta, anchorX = null, anchorY = null) {
  const next = Math.max(0.5, Math.min(5.0, +(lbState.zoom + delta).toFixed(2)));
  if (next === lbState.zoom) return;
  if (anchorX !== null && anchorY !== null) {
    const stage = document.getElementById("lightbox-stage");
    const rect = stage.getBoundingClientRect();
    const cx = anchorX - (rect.left + rect.width / 2);
    const cy = anchorY - (rect.top + rect.height / 2);
    const ratio = next / lbState.zoom;
    lbState.tx = cx - (cx - lbState.tx) * ratio;
    lbState.ty = cy - (cy - lbState.ty) * ratio;
  }
  lbState.zoom = next;
  if (lbState.zoom <= 1.0) {
    lbState.tx = 0;
    lbState.ty = 0;
  }
  applyLbTransform();
}

function showLightbox(title, caption, node) {
  const lb = document.getElementById("media-lightbox");
  const canvas = document.getElementById("lightbox-canvas");
  const titleEl = document.getElementById("lightbox-title");
  const capEl = document.getElementById("lightbox-caption");
  if (!lb || !canvas) return;
  canvas.innerHTML = "";
  canvas.appendChild(node);
  if (titleEl) titleEl.textContent = title || "Expanded View";
  if (capEl) capEl.textContent = caption || "";
  resetLbView();
  lb.hidden = false;
  lb.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

function openLightboxWithSvg(svgEl, title, caption) {
  const clone = svgEl.cloneNode(true);
  clone.removeAttribute("class");
  showLightbox(title, caption, clone);
}

function openLightboxWithImg(src, title, caption) {
  const img = document.createElement("img");
  img.src = src;
  img.alt = title || "";
  showLightbox(title, caption, img);
}

function closeLightbox() {
  const lb = document.getElementById("media-lightbox");
  if (!lb || lb.hidden) return;
  lb.hidden = true;
  lb.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
}

function bindLightboxEvents() {
  const lb = document.getElementById("media-lightbox");
  const stage = document.getElementById("lightbox-stage");
  const canvas = document.getElementById("lightbox-canvas");
  if (!lb || !stage || !canvas) return;

  document.getElementById("lb-zoom-in")?.addEventListener("click", () => stepLbZoom(0.35));
  document.getElementById("lb-zoom-out")?.addEventListener("click", () => stepLbZoom(-0.35));
  document.getElementById("lb-zoom-reset")?.addEventListener("click", resetLbView);
  document.getElementById("lb-close")?.addEventListener("click", closeLightbox);

  stage.addEventListener("wheel", (e) => {
    e.preventDefault();
    stepLbZoom(e.deltaY < 0 ? 0.25 : -0.25, e.clientX, e.clientY);
  }, { passive: false });

  stage.addEventListener("dblclick", (e) => {
    if (lbState.zoom > 1.1) {
      resetLbView();
    } else {
      stepLbZoom(1.0, e.clientX, e.clientY);
    }
  });

  stage.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    lbState.dragging = true;
    lbState.startX = e.clientX;
    lbState.startY = e.clientY;
    lbState.startTx = lbState.tx;
    lbState.startTy = lbState.ty;
    stage.classList.add("dragging");
    canvas.classList.add("dragging");
    stage.setPointerCapture(e.pointerId);
  });

  stage.addEventListener("pointermove", (e) => {
    if (!lbState.dragging) return;
    lbState.tx = lbState.startTx + (e.clientX - lbState.startX);
    lbState.ty = lbState.startTy + (e.clientY - lbState.startY);
    applyLbTransform();
  });

  const endDrag = (e) => {
    if (!lbState.dragging) return;
    lbState.dragging = false;
    stage.classList.remove("dragging");
    canvas.classList.remove("dragging");
    if (Math.hypot(e.clientX - lbState.startX, e.clientY - lbState.startY) < 4 && e.target === stage) {
      closeLightbox();
    }
  };
  stage.addEventListener("pointerup", endDrag);
  stage.addEventListener("pointercancel", endDrag);

  document.addEventListener("keydown", (e) => {
    if (lb.hidden) return;
    if (e.key === "Escape") closeLightbox();
    else if (e.key === "+" || e.key === "=") stepLbZoom(0.35);
    else if (e.key === "-") stepLbZoom(-0.35);
    else if (e.key === "0") resetLbView();
  });
}

// --- Full Interactive CSV Dataset Explorer ---
const dsCache = new Map();
const dsState = {
  url: DATASET_SOURCES[0].url,
  headers: [],
  rows: [],
  filtered: [],
  page: 1,
  pageSize: 50,
  loadedOnce: false,
};

function parseCsvText(text) {
  const lines = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n").filter((l) => l.length > 0);
  if (!lines.length) return { headers: [], rows: [] };
  const splitRow = (line) => {
    if (!line.includes('"')) return line.split(",");
    const out = [];
    let cur = "", inQ = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') {
        if (inQ && line[i + 1] === '"') { cur += '"'; i++; }
        else { inQ = !inQ; }
      } else if (ch === "," && !inQ) {
        out.push(cur); cur = "";
      } else {
        cur += ch;
      }
    }
    out.push(cur);
    return out;
  };
  const headers = splitRow(lines[0]);
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const vals = splitRow(lines[i]);
    if (vals.length === headers.length) rows.push(vals);
  }
  return { headers, rows };
}

function formatCell(val) {
  if (val === "" || val === undefined || val === null) return "";
  if (/^-?\d+\.\d{5,}$/.test(val)) {
    const num = Number(val);
    if (Number.isFinite(num)) return Math.abs(num) >= 1000 || Math.abs(num) < 1e-4 ? num.toExponential(3) : num.toFixed(4);
  }
  return val;
}

function applyDatasetFilters(resetPage = true) {
  const epSel = document.getElementById("ds-episode-filter");
  const lblSel = document.getElementById("ds-label-filter");
  const searchEl = document.getElementById("ds-search-input");
  const epVal = epSel ? epSel.value : "all";
  const lblVal = lblSel ? lblSel.value : "all";
  const q = searchEl ? searchEl.value.trim().toLowerCase() : "";

  const epIdx = dsState.headers.indexOf("episode_id");
  const lblIdx = dsState.headers.indexOf("spoof_active");

  dsState.filtered = dsState.rows.filter((r) => {
    if (epIdx >= 0 && epVal !== "all" && r[epIdx] !== epVal) return false;
    if (lblIdx >= 0 && lblVal !== "all" && r[lblIdx] !== lblVal) return false;
    if (q) {
      let matched = false;
      for (let i = 0; i < r.length; i++) {
        if (r[i].toLowerCase().includes(q)) { matched = true; break; }
      }
      if (!matched) return false;
    }
    return true;
  });

  if (resetPage) dsState.page = 1;
  renderDatasetPage();
}

function renderDatasetPage() {
  const thead = document.getElementById("ds-thead");
  const tbody = document.getElementById("ds-tbody");
  const stats = document.getElementById("ds-stats-text");
  const pills = document.getElementById("ds-split-pills");
  const pageInfo = document.getElementById("ds-page-info");
  const prevBtn = document.getElementById("ds-prev-page");
  const nextBtn = document.getElementById("ds-next-page");
  if (!thead || !tbody) return;

  const total = dsState.filtered.length;
  const totalPages = Math.max(1, Math.ceil(total / dsState.pageSize));
  dsState.page = Math.min(Math.max(1, dsState.page), totalPages);
  const startIdx = (dsState.page - 1) * dsState.pageSize;
  const endIdx = Math.min(total, startIdx + dsState.pageSize);
  const slice = dsState.filtered.slice(startIdx, endIdx);

  thead.innerHTML = `<tr><th>#</th>${dsState.headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr>`;
  if (!slice.length) {
    tbody.innerHTML = `<tr><td colspan="${dsState.headers.length + 1}" style="padding:16px;">No rows match the selected filters.</td></tr>`;
  } else {
    tbody.innerHTML = slice
      .map((row, idx) => {
        const rowNum = startIdx + idx + 1;
        return `<tr><td>${rowNum}</td>${row.map((cell) => `<td>${esc(formatCell(cell))}</td>`).join("")}</tr>`;
      })
      .join("");
  }

  const lblIdx = dsState.headers.indexOf("spoof_active");
  let nomCount = 0, spoofCount = 0;
  if (lblIdx >= 0) {
    for (const r of dsState.filtered) {
      if (r[lblIdx] === "1" || r[lblIdx] === "1.0") spoofCount++;
      else nomCount++;
    }
  }
  if (stats) {
    stats.textContent = `Showing rows ${total ? startIdx + 1 : 0}-${endIdx} of ${total.toLocaleString()} matching (${dsState.rows.length.toLocaleString()} total rows x ${dsState.headers.length} columns)`;
  }
  if (pills) {
    pills.innerHTML = lblIdx >= 0
      ? `<span class="badge badge-emerald">Nominal: ${nomCount.toLocaleString()}</span> <span class="badge badge-carmine">Spoofed: ${spoofCount.toLocaleString()}</span>`
      : `<span class="badge badge-cobalt">Columns: ${dsState.headers.length}</span>`;
  }
  if (pageInfo) pageInfo.textContent = `Page ${dsState.page} / ${totalPages}`;
  if (prevBtn) prevBtn.disabled = dsState.page <= 1;
  if (nextBtn) nextBtn.disabled = dsState.page >= totalPages;
}

async function loadDatasetUrl(url) {
  const tbody = document.getElementById("ds-tbody");
  const stats = document.getElementById("ds-stats-text");
  const dl = document.getElementById("ds-download-link");
  const sel = document.getElementById("ds-source-select");
  const epSel = document.getElementById("ds-episode-filter");
  const schemaBox = document.getElementById("ds-schema-box");

  dsState.url = url;
  dsState.loadedOnce = true;
  if (sel && sel.value !== url) sel.value = url;
  if (dl) dl.href = url;
  if (stats) stats.textContent = `Loading ${url.split("/").pop()}...`;
  if (tbody) tbody.innerHTML = `<tr><td style="padding:16px;">Loading dataset rows...</td></tr>`;

  try {
    let parsed = dsCache.get(url);
    if (!parsed) {
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const txt = await resp.text();
      parsed = parseCsvText(txt);
      dsCache.set(url, parsed);
    }
    dsState.headers = parsed.headers;
    dsState.rows = parsed.rows;

    if (schemaBox) {
      schemaBox.innerHTML = `<strong>Schema (${parsed.headers.length} columns):</strong> ${parsed.headers.map((h) => `<code>${esc(h)}</code>`).join(" ")}`;
    }
    if (epSel) {
      const epIdx = parsed.headers.indexOf("episode_id");
      if (epIdx >= 0) {
        const eps = [...new Set(parsed.rows.map((r) => r[epIdx]))].sort();
        epSel.innerHTML = `<option value="all">All Episodes (${eps.length})</option>` + eps.map((ep) => `<option value="${esc(ep)}">${esc(ep)}</option>`).join("");
        epSel.disabled = false;
      } else {
        epSel.innerHTML = `<option value="all">N/A (Summary Table)</option>`;
        epSel.disabled = true;
      }
    }
    applyDatasetFilters(true);
  } catch (err) {
    if (tbody) tbody.innerHTML = `<tr><td style="padding:16px;color:var(--carmine);">Failed to load dataset (${esc(err.message)}).</td></tr>`;
  }
}

function bindDatasetExplorer() {
  document.getElementById("ds-source-select")?.addEventListener("change", (e) => loadDatasetUrl(e.target.value));
  document.getElementById("ds-episode-filter")?.addEventListener("change", () => applyDatasetFilters(true));
  document.getElementById("ds-label-filter")?.addEventListener("change", () => applyDatasetFilters(true));
  document.getElementById("ds-search-input")?.addEventListener("input", () => applyDatasetFilters(true));
  document.getElementById("ds-page-size")?.addEventListener("change", (e) => {
    dsState.pageSize = Number(e.target.value) || 50;
    dsState.page = 1;
    renderDatasetPage();
  });
  document.getElementById("ds-prev-page")?.addEventListener("click", () => {
    if (dsState.page > 1) { dsState.page--; renderDatasetPage(); }
  });
  document.getElementById("ds-next-page")?.addEventListener("click", () => {
    const totalPages = Math.max(1, Math.ceil(dsState.filtered.length / dsState.pageSize));
    if (dsState.page < totalPages) { dsState.page++; renderDatasetPage(); }
  });
  document.getElementById("ds-toggle-schema")?.addEventListener("click", () => {
    const box = document.getElementById("ds-schema-box");
    if (box) box.style.display = box.style.display === "none" ? "block" : "none";
  });
}

function bindEvents() {
  document.addEventListener("click", (e) => {
    const tabBtn = e.target.closest("[data-tab]");
    if (tabBtn) {
      activateTab(tabBtn.dataset.tab);
      if (resolveTabId(tabBtn.dataset.tab) === "ai" && !dsState.loadedOnce) {
        loadDatasetUrl(dsState.url);
      }
      return;
    }

    const tabLink = e.target.closest("[data-tab-link]");
    if (tabLink) {
      e.preventDefault();
      activateTab(tabLink.dataset.tabLink);
      return;
    }

    const jumpBtn = e.target.closest("[data-jump]");
    if (jumpBtn) {
      activateTab(jumpBtn.dataset.jump);
      if (resolveTabId(jumpBtn.dataset.jump) === "ai" && !dsState.loadedOnce) {
        loadDatasetUrl(dsState.url);
      }
      return;
    }

    const loadBtn = e.target.closest("[data-load-csv]");
    if (loadBtn) {
      const targetUrl = loadBtn.dataset.loadCsv;
      loadDatasetUrl(targetUrl);
      document.getElementById("ds-source-select")?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }

    const subBtn = e.target.closest("[data-subview]");
    if (subBtn) {
      const target = subBtn.dataset.subview;
      subBtn.parentElement.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
      subBtn.classList.add("active");
      document.querySelectorAll(".subview").forEach((v) => {
        v.style.display = v.id === target ? "block" : "none";
      });
      if (target === "sub-dataset" && !dsState.loadedOnce) {
        loadDatasetUrl(dsState.url);
      }
      return;
    }

    const catBtn = e.target.closest("[data-cat-filter]");
    if (catBtn) {
      const target = catBtn.dataset.catFilter;
      catBtn.parentElement.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
      catBtn.classList.add("active");
      document.querySelectorAll(".research-cat-block").forEach((blk) => {
        blk.style.display = target === "all" || blk.dataset.catId === target ? "block" : "none";
      });
    }
  });

  window.addEventListener("hashchange", () => {
    const hash = window.location.hash.replace("#", "");
    if (hash) {
      activateTab(hash, false);
      if (resolveTabId(hash) === "ai" && !dsState.loadedOnce) {
        loadDatasetUrl(dsState.url);
      }
    }
  });
}

mountAllPanels();
bindEvents();
bindLightboxEvents();
bindDatasetExplorer();
const initial = window.location.hash.replace("#", "") || "overview";
activateTab(initial, false);
if (resolveTabId(initial) === "ai") {
  loadDatasetUrl(dsState.url);
}

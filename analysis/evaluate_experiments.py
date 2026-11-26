#!/usr/bin/env python3
"""Parse CSV flight logs and PX4 .ulg ULogs to extract quantitative Phase 6 metrics."""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from pyulog import ULog


REPO_ROOT = Path(__file__).resolve().parents[1]


def extract_ulog_metrics(ulg_path: Path, guardian: bool, attack_duration_s: float) -> Dict[str, Any]:
    """Read estimator_status_flags & vehicle_local_position directly from binary PX4 ULog."""
    if not ulg_path.exists():
        return {"ulog_present": False}

    ulog = ULog(str(ulg_path), ["estimator_status_flags", "vehicle_local_position"])
    out: Dict[str, Any] = {"ulog_present": True, "ulog_duration_s": round((ulog.last_timestamp - ulog.start_timestamp) * 1e-6, 2)}

    try:
        fl = ulog.get_dataset("estimator_status_flags").data
        t_s = (fl["timestamp"] - ulog.start_timestamp) * 1e-6
        end_mask = t_s >= max(0.0, float(t_s[-1]) - max(4.0, attack_duration_s * 0.5))
        if np.any(end_mask):
            out["ulog_tail_gps_fused_pct"] = round(float(100.0 * np.mean(fl["cs_gps"][end_mask] > 0)), 2)
            out["ulog_tail_of_fused_pct"] = round(float(100.0 * np.mean(fl["cs_opt_flow"][end_mask] > 0)), 2)
            out["ulog_tail_rng_fused_pct"] = round(float(100.0 * np.mean(fl["cs_rng_hgt"][end_mask] > 0)), 2)
        if guardian and np.any(fl["cs_gps"] == 0):
            # Track whether GPS cutover actually persisted inside PX4 core estimator log
            off_idx = np.where((t_s > 12.0) & (fl["cs_gps"] == 0))[0]
            out["ulog_gps_cutover_observed"] = bool(len(off_idx) > 0)
    except (KeyError, IndexError):
        pass

    return out


def evaluate_run(spec: Dict[str, Any], exp_dir: Path) -> Dict[str, Any]:
    """Compute detection latency, hijack error, trajectory RMSE, and hover drift for one run."""
    run_id = spec["run_id"]
    csv_path = exp_dir / spec["csv"]
    df = pd.read_csv(csv_path)
    df["hijack_err_xy"] = np.hypot(df["est_x"] - df["gt_x"], df["est_y"] - df["gt_y"])
    df["target_err_xy"] = np.hypot(df["gt_x"] - df["target_n"], df["gt_y"] - df["target_e"])
    df["gt_agl_m"] = -df["gt_z"]

    air = df[(df["est_xy_valid"] == 1) & (df["arming_state"] == 2) & (df["est_z"] < -1.0)].copy()

    attack_mode = spec["attack_mode"]
    guardian = bool(spec["guardian"])

    # Pre-attack nominal window metrics
    nom = air[air["spoof_active"] == 0]
    false_failover = bool(guardian and attack_mode == "none" and np.any(df["guardian_active"] == 1))

    result: Dict[str, Any] = {
        "run_id": run_id,
        "attack_mode": attack_mode,
        "guardian": guardian,
        "rate_mps": spec.get("rate_mps", 0.0),
        "offset_n": spec.get("offset_n", 0.0),
        "nominal_pre_rmse_m": round(float(np.sqrt(np.mean(nom["hijack_err_xy"] ** 2))), 3) if not nom.empty else None,
        "false_failover": false_failover,
    }

    atk = air[air["spoof_active"] == 1].sort_values("timestamp_s").copy()
    if atk.empty:
        result.update(
            {
                "detection_latency_ms": None,
                "hijack_rmse_m": round(float(np.sqrt(np.mean(air["hijack_err_xy"] ** 2))), 3),
                "max_hijack_err_m": round(float(air["hijack_err_xy"].max()), 3),
                "final_hijack_err_m": round(float(air["hijack_err_xy"].iloc[-1]), 3),
                "target_rmse_m": round(float(np.sqrt(np.mean(air["target_err_xy"] ** 2))), 3),
                "settled_hover_drift_mps": None,
                "post_failover_alt_std_m": None,
            }
        )
        ulg_stats = extract_ulog_metrics(exp_dir / f"{run_id}.ulg", guardian, attack_duration_s=10.0)
        result.update(ulg_stats)
        return result

    atk_dur = float(atk["timestamp_s"].iloc[-1] - atk["timestamp_s"].iloc[0])
    det_rows = atk[atk["guardian_active"] == 1]

    det_latency_ms: Optional[float] = None
    post_drift_m: Optional[float] = None
    settled_drift_mps: Optional[float] = None
    post_alt_std: Optional[float] = None
    post_alt_mean: Optional[float] = None

    if not det_rows.empty:
        first_det = det_rows.iloc[0]
        det_latency_ms = round(float(first_det["attack_elapsed_s"]) * 1000.0, 1)
        t_det = float(first_det["timestamp_s"])
        post = atk[atk["timestamp_s"] >= t_det].copy()
        if len(post) >= 2:
            post_drift_m = round(
                float(np.hypot(post["gt_x"].iloc[-1] - post["gt_x"].iloc[0], post["gt_y"].iloc[-1] - post["gt_y"].iloc[0])),
                3,
            )
            post_alt_std = round(float(post["gt_agl_m"].std()), 3)
            post_alt_mean = round(float(post["gt_agl_m"].mean()), 3)

        # Settled hover drift after braking deceleration (+2.0 s post-cutover)
        settled = atk[atk["timestamp_s"] >= (t_det + 2.0)].copy()
        if len(settled) >= 10:
            dt_set = max(0.1, float(settled["timestamp_s"].iloc[-1] - settled["timestamp_s"].iloc[0]))
            dist_set = float(
                np.hypot(
                    settled["gt_x"].iloc[-1] - settled["gt_x"].iloc[0],
                    settled["gt_y"].iloc[-1] - settled["gt_y"].iloc[0],
                )
            )
            settled_drift_mps = round(dist_set / dt_set, 4)

    result.update(
        {
            "attack_duration_s": round(atk_dur, 2),
            "detection_latency_ms": det_latency_ms,
            "hijack_rmse_m": round(float(np.sqrt(np.mean(atk["hijack_err_xy"] ** 2))), 3),
            "max_hijack_err_m": round(float(atk["hijack_err_xy"].max()), 3),
            "final_hijack_err_m": round(float(atk["hijack_err_xy"].iloc[-1]), 3),
            "target_rmse_m": round(float(np.sqrt(np.mean(atk["target_err_xy"] ** 2))), 3),
            "post_failover_total_drift_m": post_drift_m,
            "settled_hover_drift_mps": settled_drift_mps,
            "post_failover_alt_mean_m": post_alt_mean,
            "post_failover_alt_std_m": post_alt_std,
            "final_agl_m": round(float(atk["gt_agl_m"].iloc[-1]), 3),
            "zero_crash": bool(atk["gt_agl_m"].min() > 1.5),
        }
    )

    ulg_stats = extract_ulog_metrics(exp_dir / f"{run_id}.ulg", guardian, attack_duration_s=atk_dur)
    result.update(ulg_stats)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Phase 6 ULog & CSV experiment metrics")
    parser.add_argument("--exp-dir", default=str(REPO_ROOT / "data" / "experiments"))
    parser.add_argument("--out-json", default=str(REPO_ROOT / "analysis" / "experiment_metrics.json"))
    parser.add_argument("--out-csv", default=str(REPO_ROOT / "analysis" / "experiment_metrics.csv"))
    args = parser.parse_args()

    exp_dir = Path(args.exp_dir)
    manifest_path = exp_dir / "experiments_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    rows = [evaluate_run(spec, exp_dir) for spec in manifest]
    out_df = pd.DataFrame(rows)

    Path(args.out_json).write_text(json.dumps(rows, indent=2), encoding="utf-8")
    out_df.to_csv(args.out_csv, index=False)

    print("\n=== Phase 6 Quantitative Experiment Results (CSV + ULog) ===")
    cols = [
        "run_id",
        "guardian",
        "detection_latency_ms",
        "hijack_rmse_m",
        "max_hijack_err_m",
        "settled_hover_drift_mps",
        "post_failover_alt_std_m",
        "ulog_tail_gps_fused_pct",
    ]
    present_cols = [c for c in cols if c in out_df.columns]
    print(out_df[present_cols].to_string(index=False))
    print(f"\n[EVAL] Exported metrics -> {args.out_json} and {args.out_csv}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Train Baseline Threshold, Random Forest, and XGBoost GPS spoofing classifiers.

Enforces strict episode-level train/test isolation (zero window overlap leakage)
and uses shared causal feature extraction from gps_failsafe_pkg.feature_extractor.
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from xgboost import XGBClassifier

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "ros2_ws" / "src" / "gps_failsafe_pkg"))

from gps_failsafe_pkg.feature_extractor import FEATURE_NAMES, extract_features_dataframe  # noqa: E402
from ml.baseline_detector import ThresholdBaselineDetector  # noqa: E402


DEFAULT_TEST_EPISODES = {
    "ep_nom_04_square_fast",
    "ep_step_04_3p8m_e",
    "ep_drift_04_1p2mps_nw",
    "ep_take_04_1p6mps_se",
}


def load_raw_episodes(raw_dir: Path) -> pd.DataFrame:
    """Load all raw flight CSV logs from raw_dir, ignoring temporary files starting with '_'."""
    csv_files = sorted(p for p in raw_dir.glob("*.csv") if not p.name.startswith("_"))
    if not csv_files:
        raise FileNotFoundError(f"No episode CSVs found in {raw_dir}")
    frames = []
    for p in csv_files:
        df = pd.read_csv(p)
        if "episode_id" not in df.columns:
            df["episode_id"] = p.stem
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    print(f"[TRAIN] Loaded {len(csv_files)} raw episodes ({len(combined)} rows total).")
    return combined


def determine_test_episodes(feat_df: pd.DataFrame, raw_dir: Path) -> set[str]:
    """Read held-out test episodes from dataset_manifest.json or fall back safely."""
    manifest_path = raw_dir / "dataset_manifest.json"
    all_eps = set(feat_df["episode_id"].unique())
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        test_eps = {m["episode_id"] for m in manifest if m.get("split_hint") == "test" and m["episode_id"] in all_eps}
        if test_eps:
            return test_eps
    intersection = DEFAULT_TEST_EPISODES & all_eps
    if intersection:
        return intersection
    # Fallback: last 25% of sorted episodes
    sorted_eps = sorted(all_eps)
    n_test = max(1, len(sorted_eps) // 4)
    return set(sorted_eps[-n_test:])


def tune_baseline_threshold(X_tr: np.ndarray, y_tr: np.ndarray) -> ThresholdBaselineDetector:
    """Grid-search residual thresholds on training episodes only (minimizing FPR < 2%)."""
    best_det = ThresholdBaselineDetector(list(FEATURE_NAMES), pos_thresh=1.2, vel_thresh=0.8)
    best_f1 = -1.0
    for pt in (0.7, 0.9, 1.1, 1.3, 1.6, 2.0, 2.5):
        for vt in (0.5, 0.7, 0.9, 1.2, 1.6):
            det = ThresholdBaselineDetector(list(FEATURE_NAMES), pos_thresh=pt, vel_thresh=vt)
            pred = det.predict(X_tr)
            nom_mask = y_tr == 0
            fpr = float(np.mean(pred[nom_mask] == 1)) if np.any(nom_mask) else 0.0
            f1 = float(f1_score(y_tr, pred, zero_division=0))
            if fpr <= 0.02 and f1 > best_f1:
                best_f1 = f1
                best_det = det
    if best_f1 < 0:
        # Relax constraint if needed
        for pt in (1.0, 1.5, 2.0, 3.0):
            det = ThresholdBaselineDetector(list(FEATURE_NAMES), pos_thresh=pt, vel_thresh=1.2)
            f1 = float(f1_score(y_tr, det.predict(X_tr), zero_division=0))
            if f1 > best_f1:
                best_f1 = f1
                best_det = det
    return best_det


def cross_validate_models(
    X_tr: np.ndarray,
    y_tr: np.ndarray,
    groups_tr: np.ndarray,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, float]]:
    """Run StratifiedGroupKFold CV across training episodes and calibrate operating thresholds."""
    n_groups = len(np.unique(groups_tr))
    n_splits = min(4, n_groups)
    sgkf = StratifiedGroupKFold(n_splits=n_splits)

    oof_rf = np.zeros(len(y_tr), dtype=np.float64)
    oof_xgb = np.zeros(len(y_tr), dtype=np.float64)

    n_neg = max(1, int(np.sum(y_tr == 0)))
    n_pos = max(1, int(np.sum(y_tr == 1)))
    spw = float(n_neg / n_pos)

    for tr_idx, va_idx in sgkf.split(X_tr, y_tr, groups_tr):
        rf = RandomForestClassifier(
            n_estimators=250,
            max_depth=12,
            min_samples_leaf=3,
            class_weight="balanced",
            n_jobs=-1,
            random_state=42,
        )
        rf.fit(X_tr[tr_idx], y_tr[tr_idx])
        oof_rf[va_idx] = rf.predict_proba(X_tr[va_idx])[:, 1]

        xgb = XGBClassifier(
            n_estimators=250,
            max_depth=4,
            learning_rate=0.05,
            min_child_weight=5,
            reg_lambda=2.0,
            subsample=0.85,
            colsample_bytree=0.85,
            eval_metric="logloss",
            n_jobs=-1,
            random_state=42,
        )
        xgb.fit(X_tr[tr_idx], y_tr[tr_idx])
        oof_xgb[va_idx] = xgb.predict_proba(X_tr[va_idx])[:, 1]

    cv_metrics: Dict[str, Dict[str, float]] = {}
    rec_thresh: Dict[str, float] = {}
    for name, probs in (("random_forest", oof_rf), ("xgboost", oof_xgb)):
        best_th, best_f1 = 0.70, -1.0
        for th in np.linspace(0.45, 0.96, 52):
            pred = (probs >= th).astype(int)
            fpr = float(np.mean(pred[y_tr == 0] == 1)) if np.any(y_tr == 0) else 0.0
            score = float(f1_score(y_tr, pred, zero_division=0))
            if fpr <= 0.003 and score > best_f1:
                best_f1 = score
                best_th = float(th)
        if best_f1 < 0:
            for th in np.linspace(0.45, 0.96, 52):
                pred = (probs >= th).astype(int)
                fpr = float(np.mean(pred[y_tr == 0] == 1)) if np.any(y_tr == 0) else 0.0
                score = float(f1_score(y_tr, pred, zero_division=0))
                if fpr <= 0.01 and score > best_f1:
                    best_f1 = score
                    best_th = float(th)
        if best_f1 < 0:
            best_th = 0.70
        pred = (probs >= best_th).astype(int)
        cv_metrics[name] = {
            "oof_roc_auc": round(float(roc_auc_score(y_tr, probs)), 5),
            "oof_f1": round(float(f1_score(y_tr, pred)), 5),
            "oof_precision": round(float(precision_score(y_tr, pred, zero_division=0)), 5),
            "oof_recall": round(float(recall_score(y_tr, pred, zero_division=0)), 5),
            "oof_fpr": round(float(np.mean(pred[y_tr == 0] == 1)), 5),
            "tuned_threshold": round(best_th, 3),
        }
        rec_thresh[name] = round(best_th, 3)

    return cv_metrics, rec_thresh


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract features and train RF/XGBoost spoofing detectors")
    parser.add_argument("--raw-dir", default=str(REPO_ROOT / "data" / "raw"))
    parser.add_argument("--processed-dir", default=str(REPO_ROOT / "data" / "processed"))
    parser.add_argument("--models-dir", default=str(REPO_ROOT / "ml" / "models"))
    parser.add_argument("--window-size", type=int, default=20)
    parser.add_argument("--min-samples", type=int, default=10)
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    proc_dir = Path(args.processed_dir)
    models_dir = Path(args.models_dir)
    proc_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    raw_df = load_raw_episodes(raw_dir)
    feat_df = extract_features_dataframe(
        raw_df,
        window_size=args.window_size,
        min_samples=args.min_samples,
        airborne_only=True,
    )
    out_feat_csv = proc_dir / "features_dataset.csv"
    feat_df.to_csv(out_feat_csv, index=False)

    n_nom = int((feat_df["spoof_active"] == 0).sum())
    n_spoof = int((feat_df["spoof_active"] == 1).sum())
    print(f"[TRAIN] Feature matrix: {len(feat_df)} windows x {len(FEATURE_NAMES)} features -> {out_feat_csv}")
    print(f"[TRAIN] Class counts: nominal={n_nom}, spoofed={n_spoof} | modes={feat_df['attack_mode'].value_counts().to_dict()}")

    test_eps = determine_test_episodes(feat_df, raw_dir)
    is_test = feat_df["episode_id"].isin(test_eps)
    train_df = feat_df[~is_test].reset_index(drop=True)
    test_df = feat_df[is_test].reset_index(drop=True)

    train_eps = sorted(train_df["episode_id"].unique().tolist())
    test_eps_list = sorted(test_df["episode_id"].unique().tolist())
    print(f"[TRAIN] Episode split: {len(train_eps)} train ({len(train_df)} rows), {len(test_eps_list)} test ({len(test_df)} rows)")
    print(f"[TRAIN] Held-out test episodes: {test_eps_list}")

    X_tr = train_df[list(FEATURE_NAMES)].to_numpy(dtype=np.float64)
    y_tr = train_df["spoof_active"].to_numpy(dtype=int)
    groups_tr = train_df["episode_id"].to_numpy()

    cv_metrics, rec_thresh = cross_validate_models(X_tr, y_tr, groups_tr)
    print(f"[TRAIN] Train-CV (StratifiedGroupKFold): {json.dumps(cv_metrics, indent=2)}")

    # Fit final models on full training episodes
    baseline = tune_baseline_threshold(X_tr, y_tr)

    rf_final = RandomForestClassifier(
        n_estimators=250,
        max_depth=12,
        min_samples_leaf=3,
        class_weight="balanced",
        n_jobs=-1,
        random_state=42,
    )
    rf_final.fit(X_tr, y_tr)

    xgb_final = XGBClassifier(
        n_estimators=250,
        max_depth=4,
        learning_rate=0.05,
        min_child_weight=5,
        reg_lambda=2.0,
        subsample=0.85,
        colsample_bytree=0.85,
        eval_metric="logloss",
        n_jobs=-1,
        random_state=42,
    )
    xgb_final.fit(X_tr, y_tr)

    joblib.dump(baseline, models_dir / "baseline_threshold.joblib")
    joblib.dump(rf_final, models_dir / "rf_detector.joblib")
    joblib.dump(xgb_final, models_dir / "xgb_detector.joblib")

    metadata = {
        "feature_names": list(FEATURE_NAMES),
        "window_size": int(args.window_size),
        "min_samples": int(args.min_samples),
        "train_episodes": train_eps,
        "test_episodes": test_eps_list,
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "baseline_params": {
            "pos_feature": baseline.pos_feature,
            "pos_thresh": baseline.pos_thresh,
            "vel_feature": baseline.vel_feature,
            "vel_thresh": baseline.vel_thresh,
        },
        "recommended_thresholds": rec_thresh,
        "train_cv_metrics": cv_metrics,
    }
    meta_path = models_dir / "model_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"[TRAIN] Saved models and metadata cleanly in {models_dir}")


if __name__ == "__main__":
    main()

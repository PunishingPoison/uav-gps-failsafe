#!/usr/bin/env python3
"""Evaluate Baseline Threshold, Random Forest, and XGBoost on unseen held-out test episodes.

Computes Classification metrics, False Positive Rate, Per-Attack Recall, and Per-Episode
Detection Latency, and saves publication-ready ROC/PR, Confusion Matrix, and Feature Importance plots.
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Dict

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def compute_detection_latency(
    test_df: pd.DataFrame,
    probs: np.ndarray,
    threshold: float,
    consecutive: int = 3,
) -> Dict[str, float]:
    """Compute time from attack start to first `consecutive` positive detections per test attack episode."""
    df = test_df.copy()
    df["pred"] = (probs >= threshold).astype(int)
    latencies: Dict[str, float] = {}
    for ep_id, ep in df.groupby("episode_id", sort=False):
        atk = ep[ep["spoof_active"] == 1].sort_values("timestamp_s")
        if atk.empty:
            continue
        preds = atk["pred"].to_numpy()
        elaps = atk["attack_elapsed_s"].to_numpy()
        run = 0
        det_s = float("nan")
        for p, t_el in zip(preds, elaps):
            run = run + 1 if p == 1 else 0
            if run >= consecutive:
                det_s = float(t_el)
                break
        latencies[str(ep_id)] = round(det_s, 3)
    return latencies


def plot_roc_pr(
    y_test: np.ndarray,
    model_probs: Dict[str, np.ndarray],
    out_path: Path,
) -> None:
    """Plot side-by-side ROC and Precision-Recall curves for all detectors."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.8), dpi=200)
    styles = {
        "Threshold Baseline": ("#6c757d", "--"),
        "Random Forest": ("#1f77b4", "-"),
        "XGBoost": ("#d62728", "-"),
    }

    for label, probs in model_probs.items():
        color, ls = styles.get(label, ("#333333", "-"))
        fpr, tpr, _ = roc_curve(y_test, probs)
        roc_auc = roc_auc_score(y_test, probs)
        ax1.plot(fpr, tpr, label=f"{label} (AUC={roc_auc:.4f})", color=color, linestyle=ls, lw=2.0)

        prec, rec, _ = precision_recall_curve(y_test, probs)
        pr_auc = average_precision_score(y_test, probs)
        ax2.plot(rec, prec, label=f"{label} (AP={pr_auc:.4f})", color=color, linestyle=ls, lw=2.0)

    ax1.plot([0, 1], [0, 1], "k:", lw=1.0, alpha=0.5)
    ax1.set_xlabel("False Positive Rate")
    ax1.set_ylabel("True Positive Rate")
    ax1.set_title("ROC Curve (Unseen Test Flights)")
    ax1.legend(loc="lower right", fontsize=8.5)
    ax1.grid(alpha=0.25)

    ax2.set_xlabel("Recall")
    ax2.set_ylabel("Precision")
    ax2.set_title("Precision-Recall Curve (Unseen Test Flights)")
    ax2.legend(loc="lower left", fontsize=8.5)
    ax2.grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_confusion_matrices(
    y_test: np.ndarray,
    model_preds: Dict[str, np.ndarray],
    out_path: Path,
) -> None:
    """Plot normalized + raw count confusion matrices for all three detectors."""
    fig, axes = plt.subplots(1, len(model_preds), figsize=(12.0, 3.9), dpi=200)
    if len(model_preds) == 1:
        axes = [axes]

    for ax, (label, preds) in zip(axes, model_preds.items()):
        cm = confusion_matrix(y_test, preds, labels=[0, 1])
        cm_norm = cm.astype(float) / np.maximum(1, cm.sum(axis=1, keepdims=True))
        ax.imshow(cm_norm, cmap="Blues", vmin=0.0, vmax=1.0)
        for i in range(2):
            for j in range(2):
                txt_color = "white" if cm_norm[i, j] > 0.55 else "black"
                ax.text(
                    j,
                    i,
                    f"{cm[i, j]}\n({100 * cm_norm[i, j]:.1f}%)",
                    ha="center",
                    va="center",
                    color=txt_color,
                    fontsize=9.5,
                    fontweight="bold",
                )
        ax.set_xticks([0, 1], labels=["Nominal", "Spoofed"])
        ax.set_yticks([0, 1], labels=["Nominal", "Spoofed"])
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")
        ax.set_title(label)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_feature_importance(
    feature_names: list[str],
    rf_model,
    xgb_model,
    out_path: Path,
    top_k: int = 12,
) -> None:
    """Plot top-K most informative features for Random Forest and XGBoost."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.0, 5.2), dpi=200)

    for ax, title, imp, color in (
        (ax1, "Random Forest Top Features", rf_model.feature_importances_, "#1f77b4"),
        (ax2, "XGBoost Top Features", xgb_model.feature_importances_, "#d62728"),
    ):
        idx = np.argsort(imp)[-top_k:]
        names = [feature_names[i] for i in idx]
        vals = imp[idx]
        ax.barh(names, vals, color=color, alpha=0.88)
        ax.set_title(title)
        ax.set_xlabel("Importance")
        ax.grid(axis="x", alpha=0.25)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate trained models on unseen test flights")
    parser.add_argument("--processed-csv", default=str(REPO_ROOT / "data" / "processed" / "features_dataset.csv"))
    parser.add_argument("--models-dir", default=str(REPO_ROOT / "ml" / "models"))
    args = parser.parse_args()

    models_dir = Path(args.models_dir)
    meta = json.loads((models_dir / "model_metadata.json").read_text(encoding="utf-8"))
    feature_names = meta["feature_names"]
    test_eps = set(meta["test_episodes"])
    rec_thresh = meta.get("recommended_thresholds", {})

    df = pd.read_csv(args.processed_csv)
    test_df = df[df["episode_id"].isin(test_eps)].reset_index(drop=True)
    if test_df.empty:
        raise RuntimeError(f"Test split is empty! test_episodes={test_eps}")

    X_te = test_df[feature_names].to_numpy(dtype=np.float64)
    y_te = test_df["spoof_active"].to_numpy(dtype=int)

    baseline = joblib.load(models_dir / "baseline_threshold.joblib")
    rf = joblib.load(models_dir / "rf_detector.joblib")
    xgb = joblib.load(models_dir / "xgb_detector.joblib")

    rf_th = float(rec_thresh.get("random_forest", 0.50))
    xgb_th = float(rec_thresh.get("xgboost", 0.50))

    model_specs = [
        ("Threshold Baseline", baseline, None),
        ("Random Forest", rf, rf_th),
        ("XGBoost", xgb, xgb_th),
    ]

    model_probs: Dict[str, np.ndarray] = {}
    model_preds: Dict[str, np.ndarray] = {}
    report: Dict[str, dict] = {}

    for label, mdl, th in model_specs:
        probs = mdl.predict_proba(X_te)[:, 1]
        preds = mdl.predict(X_te) if th is None else (probs >= th).astype(int)
        model_probs[label] = probs
        model_preds[label] = preds

        nom_mask = y_te == 0
        per_mode_recall = {}
        for mode in ("step", "drift", "takeover"):
            mmask = test_df["attack_mode"] == mode
            if mmask.any():
                per_mode_recall[mode] = round(float(np.mean(preds[mmask] == 1)), 4)

        latencies = compute_detection_latency(test_df, probs, threshold=(1.0 if th is None else th) if th is not None else 0.5)
        if th is None:
            # Use native baseline decision predict for latency
            tmp = test_df.copy()
            tmp["pred"] = preds
            latencies = {}
            for ep_id, ep in tmp.groupby("episode_id", sort=False):
                atk = ep[ep["spoof_active"] == 1].sort_values("timestamp_s")
                if atk.empty:
                    continue
                run, det_s = 0, float("nan")
                for p, t_el in zip(atk["pred"].to_numpy(), atk["attack_elapsed_s"].to_numpy()):
                    run = run + 1 if p == 1 else 0
                    if run >= 3:
                        det_s = float(t_el)
                        break
                latencies[str(ep_id)] = round(det_s, 3)

        report[label] = {
            "threshold": th,
            "accuracy": round(float(accuracy_score(y_te, preds)), 4),
            "precision": round(float(precision_score(y_te, preds, zero_division=0)), 4),
            "recall": round(float(recall_score(y_te, preds, zero_division=0)), 4),
            "f1": round(float(f1_score(y_te, preds, zero_division=0)), 4),
            "roc_auc": round(float(roc_auc_score(y_te, probs)), 4),
            "pr_auc": round(float(average_precision_score(y_te, probs)), 4),
            "nominal_fpr": round(float(np.mean(preds[nom_mask] == 1)) if nom_mask.any() else 0.0, 4),
            "per_attack_recall": per_mode_recall,
            "detection_latency_s": latencies,
        }

    print("\n=== Unseen-Episode Test Evaluation Report ===")
    print(json.dumps(report, indent=2))
    (models_dir / "evaluation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    plot_roc_pr(y_te, model_probs, models_dir / "eval_roc_pr_curves.png")
    plot_confusion_matrices(y_te, model_preds, models_dir / "eval_confusion_matrices.png")
    plot_feature_importance(feature_names, rf, xgb, models_dir / "eval_feature_importance.png")
    print(f"[EVAL] Saved plots and report into {models_dir}")


if __name__ == "__main__":
    main()

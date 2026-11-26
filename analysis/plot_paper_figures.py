#!/usr/bin/env python3
"""Generate publication-quality 300-DPI academic figures from Phase 6 experiments."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]


def plot_trajectory_comparison(exp_dir: Path, out_path: Path) -> None:
    """Figure 1: Top-down XY trajectories for Step, Drift, and Takeover (Unguarded vs AI Guardian)."""
    pairs = [
        ("Step Jump (4.0 m North)", "exp_step_unguarded.csv", "exp_step_guarded.csv"),
        ("Slow Drift (2.2 m/s @ 45°)", "exp_drift_2p2_unguarded.csv", "exp_drift_2p2_guarded.csv"),
        ("Coordinated Takeover (2.2 m/s @ 180°)", "exp_takeover_unguarded.csv", "exp_takeover_guarded.csv"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.9), dpi=300)
    sq_e = [-6.0, 6.0, 6.0, -6.0, -6.0]
    sq_n = [6.0, 6.0, -6.0, -6.0, 6.0]

    for ax, (title, ung_csv, grd_csv) in zip(axes, pairs):
        ax.plot(sq_e, sq_n, "k--", lw=1.2, alpha=0.55, label="Planned Square")

        u_df = pd.read_csv(exp_dir / ung_csv)
        u_air = u_df[(u_df["arming_state"] == 2) & (u_df["est_z"] < -1.5)]
        g_df = pd.read_csv(exp_dir / grd_csv)
        g_air = g_df[(g_df["arming_state"] == 2) & (g_df["est_z"] < -1.5)]

        ax.plot(u_air["gt_y"], u_air["gt_x"], color="#d62728", lw=2.0, label="True Path (Unguarded)")
        ax.plot(u_air["est_y"], u_air["est_x"], color="#ff9896", lw=1.3, ls=":", label="Spoofed EKF Belief")

        ax.plot(g_air["gt_y"], g_air["gt_x"], color="#1f77b4", lw=2.3, label="True Path (AI Guardian)")

        u_atk = u_air[u_air["spoof_active"] == 1]
        if not u_atk.empty:
            ax.scatter(u_atk["gt_y"].iloc[0], u_atk["gt_x"].iloc[0], color="#d62728", marker="x", s=65, zorder=5, label="Attack Start (Unguarded)")
            ax.scatter(u_atk["gt_y"].iloc[-1], u_atk["gt_x"].iloc[-1], color="#8c1515", marker="o", s=55, zorder=5)

        g_det = g_air[g_air["guardian_active"] == 1]
        if not g_det.empty:
            ax.scatter(g_det["gt_y"].iloc[0], g_det["gt_x"].iloc[0], color="#2ca02c", marker="*", s=140, zorder=6, label="Guardian Cutover (Hold)")

        ax.set_title(title, fontsize=10.5, fontweight="bold")
        ax.set_xlabel("East [m]")
        ax.set_ylabel("North [m]")
        ax.grid(alpha=0.25)
        ax.axis("equal")

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=8.5, frameon=True, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("UAV Spatial Hijacking vs. AI Guardian GPS-Denied Failover Recovery", fontsize=12.5, fontweight="bold", y=1.01)
    fig.tight_layout(rect=[0.0, 0.06, 1.0, 0.97])
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_recovery_timeseries(exp_dir: Path, out_path: Path) -> None:
    """Figure 2: Time-series of hijack error, altitude/speed stabilization, and EKF2 cutover."""
    cols_spec = [
        ("Drift Attack (2.2 m/s @ 45°)", "exp_drift_2p2_unguarded.csv", "exp_drift_2p2_guarded.csv"),
        ("Coordinated Takeover (2.2 m/s @ 180°)", "exp_takeover_unguarded.csv", "exp_takeover_guarded.csv"),
    ]

    fig, axes = plt.subplots(3, 2, figsize=(13.0, 8.8), dpi=300, sharex="col")

    for col_idx, (col_title, ung_csv, grd_csv) in enumerate(cols_spec):
        u = pd.read_csv(exp_dir / ung_csv)
        g = pd.read_csv(exp_dir / grd_csv)

        def align_atk(df: pd.DataFrame) -> pd.DataFrame:
            sub = df[(df["arming_state"] == 2) & (df["est_z"] < -1.5)].copy()
            t0 = sub.loc[sub["spoof_active"] == 1, "timestamp_s"].iloc[0]
            sub["t_rel"] = sub["timestamp_s"] - t0
            sub["hijack_err"] = np.hypot(sub["est_x"] - sub["gt_x"], sub["est_y"] - sub["gt_y"])
            sub["gt_speed"] = np.hypot(sub["gt_vx"], sub["gt_vy"])
            return sub[sub["t_rel"] >= -5.0]

        ua = align_atk(u)
        ga = align_atk(g)
        t_det = float(ga.loc[ga["guardian_active"] == 1, "t_rel"].iloc[0])

        # Row 0: Hijack localization divergence
        ax0 = axes[0, col_idx]
        ax0.plot(ua["t_rel"], ua["hijack_err"], color="#d62728", lw=2.0, label="Unguarded ||Est - GT||")
        ax0.plot(ga["t_rel"], ga["hijack_err"], color="#1f77b4", lw=2.2, label="AI Guardian ||Est - GT||")
        ax0.axvline(0.0, color="k", ls="--", lw=1.1, label="Attack Start (t=0s)")
        ax0.axvline(t_det, color="#2ca02c", ls="-.", lw=1.5, label=f"Failover Cutover (t={t_det:.2f}s)")
        ax0.set_title(col_title, fontsize=11, fontweight="bold")
        ax0.set_ylabel("Localization Error [m]")
        ax0.grid(alpha=0.25)
        ax0.legend(loc="upper left", fontsize=8.0)

        # Row 1: Ground speed + Altitude AGL
        ax1 = axes[1, col_idx]
        ax1.plot(ga["t_rel"], -ga["gt_z"], color="#17becf", lw=2.0, label="Guardian AGL [m]")
        ax1.plot(ga["t_rel"], ga["gt_speed"], color="#ff7f0e", lw=1.8, label="Guardian Ground Speed [m/s]")
        ax1.axvline(0.0, color="k", ls="--", lw=1.1)
        ax1.axvline(t_det, color="#2ca02c", ls="-.", lw=1.5)
        ax1.set_ylabel("Altitude [m] / Speed [m/s]")
        ymax_agl = max(5.5, float((-ga["gt_z"]).max()) + 1.2)
        ax1.set_ylim(-0.2, ymax_agl)
        ax1.grid(alpha=0.25)
        ax1.legend(loc="upper right", fontsize=8.0)

        # Row 2: PX4 EKF2 control status flags
        ax2 = axes[2, col_idx]
        ax2.step(ga["t_rel"], ga["cs_gps"], where="post", color="#d62728", lw=2.0, label="cs_gps (GPS Fusion)")
        ax2.step(ga["t_rel"], ga["cs_opt_flow"] * 0.96, where="post", color="#1f77b4", lw=1.8, ls="--", label="cs_opt_flow (Optical Flow)")
        ax2.step(ga["t_rel"], ga["cs_rng_hgt"] * 0.92, where="post", color="#2ca02c", lw=1.8, ls=":", label="cs_rng_hgt (1D LiDAR)")
        ax2.axvline(0.0, color="k", ls="--", lw=1.1)
        ax2.axvline(t_det, color="#2ca02c", ls="-.", lw=1.5)
        ax2.set_yticks([0, 1], labels=["OFF (0)", "ON (1)"])
        ax2.set_xlabel("Time Since Spoofing Injection [s]")
        ax2.set_ylabel("EKF2 Active Flags")
        ax2.grid(alpha=0.25)
        ax2.legend(loc="center right", fontsize=8.0)

    fig.suptitle("Real-Time Spoofing Interception & Sensor Failover Dynamics", fontsize=12.5, fontweight="bold", y=0.995)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_ablation_metrics(metrics_json: Path, out_path: Path) -> None:
    """Figure 3: Quantitative comparison across attack modes and drift rates."""
    rows = json.loads(metrics_json.read_text(encoding="utf-8"))
    by_id = {r["run_id"]: r for r in rows}

    labels = ["Step\n(4.0 m)", "Slow Drift\n(0.8 m/s)", "Fast Drift\n(2.2 m/s)", "Takeover\n(2.2 m/s)"]
    pairs = [
        ("exp_step_unguarded", "exp_step_guarded"),
        ("exp_drift_0p8_unguarded", "exp_drift_0p8_guarded"),
        ("exp_drift_2p2_unguarded", "exp_drift_2p2_guarded"),
        ("exp_takeover_unguarded", "exp_takeover_guarded"),
    ]

    ung_peak = [by_id[u]["max_hijack_err_m"] for u, _ in pairs]
    grd_peak = [by_id[g]["max_hijack_err_m"] for _, g in pairs]
    ung_rmse = [by_id[u]["hijack_rmse_m"] for u, _ in pairs]
    grd_rmse = [by_id[g]["hijack_rmse_m"] for _, g in pairs]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.2, 4.6), dpi=300)
    x = np.arange(len(labels))
    w = 0.36

    b1 = ax1.bar(x - w / 2, ung_peak, width=w, color="#d62728", alpha=0.88, label="Unguarded (GPS Only)")
    b2 = ax1.bar(x + w / 2, grd_peak, width=w, color="#1f77b4", alpha=0.90, label="AI Guardian (GPS -> OF+LiDAR)")
    ax1.bar_label(b1, fmt="%.1fm", padding=2, fontsize=8.0)
    ax1.bar_label(b2, fmt="%.2fm", padding=2, fontsize=8.0)
    ax1.set_xticks(x, labels)
    ax1.set_ylabel("Peak Hijack Deviation ||Est - GT|| [m]")
    ax1.set_title("Peak Localization Excursion During Attack")
    ax1.grid(axis="y", alpha=0.25)
    ax1.legend(fontsize=8.5)

    # Panel B: Drift-rate & attack latency vs settled hover drift
    grd_ids = ["exp_step_guarded", "exp_drift_0p8_guarded", "exp_drift_1p5_guarded", "exp_drift_2p2_guarded", "exp_takeover_guarded"]
    g_labels = ["Step\n4.0 m", "Drift\n0.8 m/s", "Drift\n1.5 m/s", "Drift\n2.2 m/s", "Takeover\n2.2 m/s"]
    lat_ms = [by_id[gid]["detection_latency_ms"] for gid in grd_ids]
    drift_cms = [100.0 * (by_id[gid]["settled_hover_drift_mps"] or 0.0) for gid in grd_ids]

    xg = np.arange(len(grd_ids))
    ax2_r = ax2.twinx()
    bars = ax2.bar(xg - 0.18, lat_ms, width=0.35, color="#2ca02c", alpha=0.85, label="Detection Latency [ms]")
    bars2 = ax2_r.bar(xg + 0.18, drift_cms, width=0.35, color="#ff7f0e", alpha=0.85, label="Settled Hover Drift [cm/s]")
    ax2.bar_label(bars, fmt="%.0f", padding=2, fontsize=8.0)
    ax2_r.bar_label(bars2, fmt="%.1f", padding=2, fontsize=8.0)
    ax2.set_xticks(xg, g_labels)
    ax2.set_ylabel("Detection Latency [ms]", color="#2ca02c")
    ax2_r.set_ylabel("Settled Post-Failover Drift [cm/s]", color="#ff7f0e")
    ax2.set_ylim(0, max(lat_ms) * 1.32)
    ax2_r.set_ylim(0, max(12.0, max(drift_cms) * 1.45))
    ax2.set_title("AI Guardian Latency & Settled Optical-Flow Hold Drift")
    ax2.grid(axis="y", alpha=0.25)
    h1, l1 = ax2.get_legend_handles_labels()
    h2, l2 = ax2_r.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8.0)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Phase 6 academic paper figures")
    parser.add_argument("--exp-dir", default=str(REPO_ROOT / "data" / "experiments"))
    parser.add_argument("--metrics-json", default=str(REPO_ROOT / "analysis" / "experiment_metrics.json"))
    parser.add_argument("--fig-dir", default=str(REPO_ROOT / "analysis" / "figures"))
    args = parser.parse_args()

    exp_dir = Path(args.exp_dir)
    fig_dir = Path(args.fig_dir)
    fig_dir.mkdir(parents=True, exist_ok=True)

    plot_trajectory_comparison(exp_dir, fig_dir / "fig1_trajectory_comparison.png")
    plot_recovery_timeseries(exp_dir, fig_dir / "fig2_recovery_timeseries.png")
    plot_ablation_metrics(Path(args.metrics_json), fig_dir / "fig3_ablation_metrics.png")
    print(f"[PLOT] Saved publication figures into {fig_dir}")


if __name__ == "__main__":
    main()

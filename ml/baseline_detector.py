#!/usr/bin/env python3
"""Simple threshold-based GPS spoofing baseline detector for ML benchmarking."""

import numpy as np


class ThresholdBaselineDetector:
    """Rule-based detector thresholding GPS-vs-EKF2 position and velocity residuals."""

    def __init__(
        self,
        feature_names: list[str],
        pos_feature: str = "pos_res_xy_curr",
        vel_feature: str = "vel_res_xy_curr",
        pos_thresh: float = 1.2,
        vel_thresh: float = 0.8,
    ) -> None:
        self.feature_names = list(feature_names)
        self.pos_feature = pos_feature
        self.vel_feature = vel_feature
        self.pos_thresh = float(pos_thresh)
        self.vel_thresh = float(vel_thresh)
        self.pos_idx = self.feature_names.index(pos_feature)
        self.vel_idx = self.feature_names.index(vel_feature)

    def decision_score(self, X: np.ndarray) -> np.ndarray:
        """Continuous normalized anomaly score (>1.0 triggers positive classification)."""
        arr = np.asarray(X, dtype=np.float64)
        p_norm = arr[:, self.pos_idx] / max(1e-6, self.pos_thresh)
        v_norm = arr[:, self.vel_idx] / max(1e-6, self.vel_thresh)
        return np.maximum(p_norm, v_norm)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Smooth logistic mapping around score=1.0 for ROC/PR evaluation."""
        score = self.decision_score(X)
        logits = np.clip(3.5 * (score - 1.0), -20.0, 20.0)
        p1 = 1.0 / (1.0 + np.exp(-logits))
        return np.column_stack([1.0 - p1, p1])

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self.decision_score(X) >= 1.0).astype(int)

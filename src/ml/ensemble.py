"""
ML Ensemble — XGBoost (primary) + IsolationForest (unsupervised backup).
Produces fraud probability score + SHAP feature importance for explainability.

Production notes:
  - XGBoost is primary: train on labelled data (IEEE-CIS or your own).
  - IsolationForest catches zero-day fraud patterns not in training data.
  - SHAP is computed only when XGBoost is trained (adds ~5ms per prediction).
  - Model version is stored alongside predictions for audit trails.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.ensemble import IsolationForest

from ..core.models import FeatureVector

logger = logging.getLogger(__name__)

# Optional imports — degrade gracefully if not installed
try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False
    logger.warning("xgboost not installed — ML ensemble will use IsolationForest only")

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("shap not installed — SHAP explanations will be disabled")


VERSION = "1.0.0"


# ──────────────────────────────────────────────
# IsolationForest Wrapper
# ──────────────────────────────────────────────

class IsoForestDetector:
    """
    Unsupervised anomaly detector.
    Trains on the first N transactions, then scores each new one.
    Acts as a safety net when XGBoost is unavailable or undertrained.
    """

    MIN_SAMPLES = 50

    def __init__(self, contamination: float = 0.05) -> None:
        self._model = IsolationForest(
            contamination=contamination,
            n_estimators=100,
            random_state=42,
            n_jobs=-1,
        )
        self._buffer: List[List[float]] = []
        self._trained = False
        self._train_count = 0

    def score(self, features: FeatureVector) -> float:
        """Return anomaly score 0–1. Higher = more anomalous."""
        vec = features.to_array()
        self._buffer.append(vec)

        if len(self._buffer) < self.MIN_SAMPLES:
            # Not enough data yet — use heuristic fallback
            return self._heuristic_score(features)

        # Retrain every 100 samples
        if not self._trained or len(self._buffer) % 100 == 0:
            X = np.array(self._buffer[-1000:])  # cap at last 1000
            self._model.fit(X)
            self._trained = True
            self._train_count += 1
            logger.debug("IsoForest retrained on %d samples (count=%d)", len(X), self._train_count)

        arr = np.array([vec])
        raw = self._model.score_samples(arr)[0]  # more negative = more anomalous
        # Convert to 0–1: typical range is [-0.6, 0.1]
        normalized = float(np.clip((-raw - 0.1) / 0.5, 0.0, 1.0))
        return normalized

    @property
    def is_warm(self) -> bool:
        return self._trained

    @staticmethod
    def _heuristic_score(f: FeatureVector) -> float:
        """Simple scoring when model not yet trained."""
        score = 0.0
        if f.amount_zscore > 3.0:
            score += 0.3
        if f.is_new_device:
            score += 0.15
        if f.is_new_location:
            score += 0.15
        if f.merchant_risk_score > 0.7:
            score += 0.2
        if f.txn_count_1h > 8:
            score += 0.2
        return min(score, 1.0)


# ──────────────────────────────────────────────
# XGBoost Wrapper
# ──────────────────────────────────────────────

class XGBDetector:
    """
    Supervised XGBoost classifier.
    Requires labelled training data. Until trained, returns None (caller falls back).
    """

    def __init__(self) -> None:
        self._model: Optional["xgb.XGBClassifier"] = None
        self._explainer: Optional[object] = None  # shap.TreeExplainer
        self._feature_names = FeatureVector.FEATURE_NAMES

        if XGB_AVAILABLE:
            self._model = xgb.XGBClassifier(
                n_estimators=300,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=20,   # fraud is ~5% of data → upweight
                use_label_encoder=False,
                eval_metric="auc",
                random_state=42,
                n_jobs=-1,
            )

    def train(self, X: np.ndarray, y: np.ndarray) -> Dict:
        """
        Train on labelled dataset.
        X shape: (n_samples, n_features), y: binary 0/1.
        Returns basic training metrics.
        """
        if not XGB_AVAILABLE or self._model is None:
            raise RuntimeError("xgboost is not installed")

        t0 = time.time()
        self._model.fit(X, y)

        # Build SHAP explainer
        if SHAP_AVAILABLE:
            self._explainer = shap.TreeExplainer(self._model)
            logger.info("SHAP explainer built")

        elapsed = time.time() - t0
        logger.info("XGBoost trained on %d samples in %.1fs", len(X), elapsed)
        return {"n_samples": len(X), "train_seconds": round(elapsed, 2)}

    def score(self, features: FeatureVector) -> Optional[float]:
        """Return fraud probability 0–1, or None if not yet trained."""
        if self._model is None or not self._is_fitted():
            return None

        arr = np.array([features.to_array()])
        prob = float(self._model.predict_proba(arr)[0][1])
        return prob

    def explain(self, features: FeatureVector, top_n: int = 5) -> List[Dict[str, float]]:
        """
        Return top N SHAP feature importances for a single prediction.
        Format: [{"feature": "amount_zscore", "shap_value": 0.32}, ...]
        """
        if not SHAP_AVAILABLE or self._explainer is None:
            return []

        arr = np.array([features.to_array()])
        try:
            shap_vals = self._explainer.shap_values(arr)
            # For binary classifier shap returns list[2]; take class-1
            if isinstance(shap_vals, list):
                vals = shap_vals[1][0]
            else:
                vals = shap_vals[0]

            pairs = sorted(
                zip(self._feature_names, vals),
                key=lambda x: abs(x[1]),
                reverse=True,
            )
            return [{"feature": n, "shap_value": round(float(v), 4)} for n, v in pairs[:top_n]]
        except Exception as exc:
            logger.warning("SHAP explanation failed: %s", exc)
            return []

    def _is_fitted(self) -> bool:
        try:
            from sklearn.utils.validation import check_is_fitted
            check_is_fitted(self._model)
            return True
        except Exception:
            return False


# ──────────────────────────────────────────────
# Ensemble
# ──────────────────────────────────────────────

class MLEnsemble:
    """
    Combines XGBoost + IsolationForest into a single score.

    Weighting strategy:
      - If XGBoost is trained: 0.70 * xgb + 0.30 * iso
      - If XGBoost not trained: 1.00 * iso  (graceful degradation)
    """

    XGB_WEIGHT = 0.70
    ISO_WEIGHT = 0.30

    def __init__(self) -> None:
        self.xgb = XGBDetector()
        self.iso = IsoForestDetector()
        self.version = VERSION

    def score(self, features: FeatureVector) -> Tuple[float, List[Dict]]:
        """
        Returns (ensemble_score 0–1, shap_top_features).
        """
        iso_score = self.iso.score(features)
        xgb_score = self.xgb.score(features)
        top_features = self.xgb.explain(features)

        if xgb_score is not None:
            final = self.XGB_WEIGHT * xgb_score + self.ISO_WEIGHT * iso_score
        else:
            final = iso_score

        return round(min(final, 1.0), 4), top_features

    def train_xgb(self, X: np.ndarray, y: np.ndarray) -> Dict:
        """Train XGBoost on labelled data. Call once on startup if model exists."""
        return self.xgb.train(X, y)

    @property
    def xgb_ready(self) -> bool:
        return self.xgb._is_fitted()

    @property
    def iso_warm(self) -> bool:
        return self.iso.is_warm

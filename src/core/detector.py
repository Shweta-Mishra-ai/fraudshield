"""
FraudDetector — main orchestrator.
Wires together: FeatureEngineer → RuleEngine → MLEnsemble → GraphEngine
and returns a complete FraudResult with latency tracking.

Ensemble weighting (tunable in config):
  final_score = 0.40 * rule_score + 0.45 * ml_score + 0.15 * graph_score
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from .features import FeatureEngineer
from .graph import FraudGraphEngine
from .models import Decision, FraudResult, RiskLevel, Transaction
from .rules import RuleEngine
from ..ml.ensemble import MLEnsemble

logger = logging.getLogger(__name__)

# ── Ensemble weights ──────────────────────────────────────────────────────
RULE_WEIGHT  = 0.40
ML_WEIGHT    = 0.45
GRAPH_WEIGHT = 0.15


class FraudDetector:
    """
    Single entry-point for evaluating a transaction.

    Usage:
        detector = FraudDetector()
        result = detector.analyze(transaction)
    """

    def __init__(
        self,
        rule_engine:  Optional[RuleEngine]      = None,
        ml_ensemble:  Optional[MLEnsemble]      = None,
        graph_engine: Optional[FraudGraphEngine] = None,
        feature_eng:  Optional[FeatureEngineer]  = None,
    ) -> None:
        self.rules    = rule_engine  or RuleEngine()
        self.ml       = ml_ensemble  or MLEnsemble()
        self.graph    = graph_engine or FraudGraphEngine()
        self.features = feature_eng  or FeatureEngineer()
        self._total_analyzed = 0

    # ──────────────────────────────────────────────────────────────────────
    # Main API
    # ──────────────────────────────────────────────────────────────────────

    def analyze(self, tx: Transaction) -> FraudResult:
        """
        Evaluate a single transaction end-to-end.
        Returns FraudResult within ~10–50ms (no Kafka/DB calls here).
        """
        t_start = time.perf_counter()

        try:
            result = self._analyze_internal(tx)
        except Exception as exc:
            logger.error("FraudDetector.analyze failed for tx %s: %s", tx.transaction_id, exc, exc_info=True)
            # Fail-open: return LOW risk to avoid blocking legitimate traffic on errors
            result = FraudResult(
                transaction_id = tx.transaction_id,
                is_fraud       = False,
                score          = 0.0,
                risk_level     = RiskLevel.LOW,
                decision       = Decision.ALLOW,
                explanation_text = f"Evaluation error (fail-open): {exc}",
                model_version  = self.ml.version,
            )

        result.latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
        self._total_analyzed += 1

        logger.debug(
            "tx=%s score=%.3f decision=%s latency=%.1fms",
            tx.transaction_id[:8], result.score, result.decision.value, result.latency_ms
        )
        return result

    # ──────────────────────────────────────────────────────────────────────
    # Internal pipeline
    # ──────────────────────────────────────────────────────────────────────

    def _analyze_internal(self, tx: Transaction) -> FraudResult:
        # ── 1. Graph score (before feature extraction, for ring features) ──
        graph_score = self.graph.user_ring_score(tx.user_id, tx.device_id, tx.ip_address)

        # ── 2. Feature extraction ─────────────────────────────────────────
        fvec = self.features.extract(tx, graph_score=graph_score)

        # ── 3. Rule engine ────────────────────────────────────────────────
        rule_score, rule_results = self.rules.evaluate(tx, fvec)

        # ── 4. ML ensemble ────────────────────────────────────────────────
        ml_score, top_features = self.ml.score(fvec)

        # ── 5. Ensemble blend ─────────────────────────────────────────────
        final_score = (
            RULE_WEIGHT  * rule_score +
            ML_WEIGHT    * ml_score   +
            GRAPH_WEIGHT * graph_score
        )
        final_score = round(min(final_score, 1.0), 4)

        # ── 6. Risk classification ────────────────────────────────────────
        risk_level = RiskLevel.from_score(final_score)
        decision   = Decision.from_score(final_score)
        is_fraud   = decision != Decision.ALLOW

        # ── 7. Human-readable explanation ─────────────────────────────────
        explanation = self._build_explanation(
            final_score, rule_score, ml_score, graph_score,
            rule_results, top_features
        )

        # ── 8. Update state (AFTER scoring to avoid data leakage) ─────────
        self.features.update(tx)
        self.graph.add_transaction(tx)

        return FraudResult(
            transaction_id = tx.transaction_id,
            is_fraud       = is_fraud,
            score          = final_score,
            risk_level     = risk_level,
            decision       = decision,
            rule_results   = rule_results,
            top_features   = top_features,
            explanation_text = explanation,
            rule_score     = rule_score,
            ml_score       = ml_score,
            graph_score    = graph_score,
            model_version  = self.ml.version,
        )

    @staticmethod
    def _build_explanation(
        final_score, rule_score, ml_score, graph_score,
        rule_results, top_features
    ) -> str:
        parts = [f"Ensemble score: {final_score:.3f} "
                 f"(rules={rule_score:.2f}, ml={ml_score:.2f}, graph={graph_score:.2f})."]

        triggered = [r for r in rule_results if r.triggered]
        if triggered:
            reasons = "; ".join(r.reason for r in triggered[:3])
            parts.append(f"Rules triggered: {reasons}.")

        if top_features:
            top = top_features[0]
            parts.append(f"Top ML signal: {top['feature']} (SHAP {top['shap_value']:+.3f}).")

        if graph_score > 0.5:
            parts.append(f"Graph ring score {graph_score:.2f} — shared device/IP detected.")

        return " ".join(parts)

    # ──────────────────────────────────────────────────────────────────────
    # Stats
    # ──────────────────────────────────────────────────────────────────────

    def get_system_status(self) -> dict:
        return {
            "total_analyzed":  self._total_analyzed,
            "xgb_trained":     self.ml.xgb_ready,
            "iso_warm":        self.ml.iso_warm,
            "graph_stats":     self.graph.get_stats(),
            "model_version":   self.ml.version,
        }

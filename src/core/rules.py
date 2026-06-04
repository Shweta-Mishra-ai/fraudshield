"""
Rule Engine — deterministic, interpretable fraud rules.
Each rule produces a RuleResult with score + human-readable evidence.
Rules are layered ON TOP of ML; they catch known patterns instantly
without needing training data (velocity abuse, impossible travel, etc.).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List

from .models import FeatureVector, RuleResult, Transaction

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Base Rule
# ──────────────────────────────────────────────

class Rule(ABC):
    name: str
    description: str
    weight: float = 1.0   # contribution to ensemble

    @abstractmethod
    def evaluate(self, tx: Transaction, features: FeatureVector) -> RuleResult:
        """Return a RuleResult. Must never raise."""
        ...


# ──────────────────────────────────────────────
# Concrete Rules
# ──────────────────────────────────────────────

class HighAmountRule(Rule):
    name = "High Value Transaction"
    description = "Amount significantly exceeds normal thresholds"

    def __init__(self, critical: float = 10_000, high: float = 5_000):
        self.critical = critical
        self.high = high

    def evaluate(self, tx: Transaction, features: FeatureVector) -> RuleResult:
        if tx.amount >= self.critical:
            return RuleResult(
                rule_name=self.name, triggered=True, score=1.0,
                reason=f"Amount ${tx.amount:,.0f} exceeds critical threshold ${self.critical:,.0f}",
                evidence={"amount": tx.amount, "threshold": self.critical},
            )
        if tx.amount >= self.high:
            return RuleResult(
                rule_name=self.name, triggered=True, score=0.7,
                reason=f"Amount ${tx.amount:,.0f} exceeds high-risk threshold ${self.high:,.0f}",
                evidence={"amount": tx.amount, "threshold": self.high},
            )
        return RuleResult(rule_name=self.name, triggered=False, score=0.0, reason="Amount within normal range")


class AmountZScoreRule(Rule):
    name = "Unusual Amount for User"
    description = "Transaction amount is a statistical outlier vs user's own history"

    def __init__(self, z_critical: float = 4.0, z_high: float = 2.5):
        self.z_critical = z_critical
        self.z_high = z_high

    def evaluate(self, tx: Transaction, features: FeatureVector) -> RuleResult:
        z = features.amount_zscore
        if z >= self.z_critical:
            return RuleResult(
                rule_name=self.name, triggered=True, score=0.9,
                reason=f"Amount is {z:.1f}σ above user's average (extreme outlier)",
                evidence={"z_score": round(z, 2)},
            )
        if z >= self.z_high:
            return RuleResult(
                rule_name=self.name, triggered=True, score=0.6,
                reason=f"Amount is {z:.1f}σ above user's average",
                evidence={"z_score": round(z, 2)},
            )
        return RuleResult(rule_name=self.name, triggered=False, score=0.0, reason="Amount normal for this user")


class VelocityRule(Rule):
    name = "Velocity Abuse"
    description = "Too many transactions in a short time window"

    def __init__(self, max_1h: int = 10, max_24h: int = 30):
        self.max_1h  = max_1h
        self.max_24h = max_24h

    def evaluate(self, tx: Transaction, features: FeatureVector) -> RuleResult:
        if features.txn_count_1h >= self.max_1h:
            return RuleResult(
                rule_name=self.name, triggered=True, score=0.85,
                reason=f"{features.txn_count_1h} transactions in last 1 hour (limit {self.max_1h})",
                evidence={"count_1h": features.txn_count_1h, "limit": self.max_1h},
            )
        if features.txn_count_24h >= self.max_24h:
            return RuleResult(
                rule_name=self.name, triggered=True, score=0.6,
                reason=f"{features.txn_count_24h} transactions in last 24 hours (limit {self.max_24h})",
                evidence={"count_24h": features.txn_count_24h, "limit": self.max_24h},
            )
        return RuleResult(rule_name=self.name, triggered=False, score=0.0, reason="Transaction velocity normal")


class NewLocationRule(Rule):
    name = "New Country"
    description = "First transaction from this country for this user"

    def evaluate(self, tx: Transaction, features: FeatureVector) -> RuleResult:
        if features.is_new_location and tx.amount > 500:
            return RuleResult(
                rule_name=self.name, triggered=True, score=0.65,
                reason=f"First transaction from {tx.location} with high amount ${tx.amount:,.0f}",
                evidence={"location": tx.location, "amount": tx.amount},
            )
        if features.is_new_location:
            return RuleResult(
                rule_name=self.name, triggered=True, score=0.3,
                reason=f"First transaction ever from {tx.location}",
                evidence={"location": tx.location},
            )
        return RuleResult(rule_name=self.name, triggered=False, score=0.0, reason="Known location for user")


class NewDeviceRule(Rule):
    name = "New Device"
    description = "Transaction from a device never seen for this user"

    def evaluate(self, tx: Transaction, features: FeatureVector) -> RuleResult:
        if features.is_new_device and features.is_new_location:
            return RuleResult(
                rule_name=self.name, triggered=True, score=0.8,
                reason="New device AND new location simultaneously (impossible travel risk)",
                evidence={"device_id": tx.device_id, "location": tx.location},
            )
        if features.is_new_device:
            return RuleResult(
                rule_name=self.name, triggered=True, score=0.35,
                reason=f"Transaction from new device {tx.device_id}",
                evidence={"device_id": tx.device_id},
            )
        return RuleResult(rule_name=self.name, triggered=False, score=0.0, reason="Known device for user")


class NightTimeHighValueRule(Rule):
    name = "Night-Time High Value"
    description = "Large transaction in off-hours (00:00–05:59 UTC)"

    def __init__(self, threshold: float = 2_000):
        self.threshold = threshold

    def evaluate(self, tx: Transaction, features: FeatureVector) -> RuleResult:
        if features.is_night and tx.amount >= self.threshold:
            return RuleResult(
                rule_name=self.name, triggered=True, score=0.7,
                reason=f"${tx.amount:,.0f} transaction at {features.hour_of_day:02d}:xx UTC (off-hours)",
                evidence={"hour": features.hour_of_day, "amount": tx.amount},
            )
        return RuleResult(rule_name=self.name, triggered=False, score=0.0, reason="Normal time window")


class HighRiskMerchantRule(Rule):
    name = "High-Risk Merchant Category"
    description = "Merchant category is statistically associated with fraud"

    def evaluate(self, tx: Transaction, features: FeatureVector) -> RuleResult:
        score = features.merchant_risk_score
        if score >= 0.8:
            return RuleResult(
                rule_name=self.name, triggered=True, score=score,
                reason=f"Merchant category '{tx.merchant_category}' is very high risk (score {score:.2f})",
                evidence={"category": tx.merchant_category, "risk_score": score},
            )
        if score >= 0.6:
            return RuleResult(
                rule_name=self.name, triggered=True, score=score * 0.7,
                reason=f"Merchant category '{tx.merchant_category}' is elevated risk",
                evidence={"category": tx.merchant_category, "risk_score": score},
            )
        return RuleResult(rule_name=self.name, triggered=False, score=0.0, reason="Merchant category low risk")


class SharedDeviceRingRule(Rule):
    name = "Shared Device / Fraud Ring"
    description = "Multiple users transacting through same device or IP"

    def __init__(self, device_threshold: int = 3, ip_threshold: int = 5):
        self.device_threshold = device_threshold
        self.ip_threshold     = ip_threshold

    def evaluate(self, tx: Transaction, features: FeatureVector) -> RuleResult:
        if features.shared_device_user_count >= self.device_threshold:
            return RuleResult(
                rule_name=self.name, triggered=True, score=0.9,
                reason=f"Device shared by {features.shared_device_user_count} users (fraud ring indicator)",
                evidence={"shared_users": features.shared_device_user_count, "device": tx.device_id},
            )
        if features.shared_ip_user_count >= self.ip_threshold:
            return RuleResult(
                rule_name=self.name, triggered=True, score=0.75,
                reason=f"IP address used by {features.shared_ip_user_count} different users",
                evidence={"shared_users": features.shared_ip_user_count, "ip": tx.ip_address},
            )
        return RuleResult(rule_name=self.name, triggered=False, score=0.0, reason="No shared device/IP rings detected")


# ──────────────────────────────────────────────
# Rule Engine
# ──────────────────────────────────────────────

class RuleEngine:
    """
    Evaluates all rules and returns an aggregated score + list of results.
    Uses weighted maximum (not sum) to avoid double-counting correlated rules.
    """

    def __init__(self, rules: List[Rule] | None = None) -> None:
        self.rules: List[Rule] = rules or self._default_rules()

    def evaluate(self, tx: Transaction, features: FeatureVector) -> tuple[float, List[RuleResult]]:
        """
        Returns (aggregate_score 0–1, list[RuleResult]).
        Score is the weighted max across all triggered rules.
        """
        results: List[RuleResult] = []
        max_score = 0.0

        for rule in self.rules:
            try:
                result = rule.evaluate(tx, features)
                results.append(result)
                if result.triggered:
                    weighted = result.score * getattr(rule, "weight", 1.0)
                    max_score = max(max_score, weighted)
            except Exception as exc:
                logger.error("Rule %s raised exception: %s", rule.name, exc, exc_info=True)
                results.append(RuleResult(
                    rule_name=rule.name, triggered=False, score=0.0,
                    reason=f"Rule evaluation failed: {exc}",
                ))

        return min(max_score, 1.0), results

    @staticmethod
    def _default_rules() -> List[Rule]:
        return [
            HighAmountRule(),
            AmountZScoreRule(),
            VelocityRule(),
            NewLocationRule(),
            NewDeviceRule(),
            NightTimeHighValueRule(),
            HighRiskMerchantRule(),
            SharedDeviceRingRule(),
        ]

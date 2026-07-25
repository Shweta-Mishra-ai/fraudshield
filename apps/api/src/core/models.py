"""
Core data models for the Fraud Detection System.
Defines Transaction, FraudResult, and supporting enums
with strict validation and serialization support.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @classmethod
    def from_score(cls, score: float) -> "RiskLevel":
        if score >= 0.85:
            return cls.CRITICAL
        if score >= 0.65:
            return cls.HIGH
        if score >= 0.35:
            return cls.MEDIUM
        return cls.LOW


class Decision(str, Enum):
    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"

    @classmethod
    def from_score(cls, score: float) -> "Decision":
        if score >= 0.8:
            return cls.BLOCK
        if score >= 0.4:
            return cls.REVIEW
        return cls.ALLOW


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    INR = "INR"
    JPY = "JPY"
    CAD = "CAD"
    AUD = "AUD"


# ──────────────────────────────────────────────
# Transaction
# ──────────────────────────────────────────────


@dataclass
class Transaction:
    """
    Represents a single financial transaction.
    All fields are validated on creation.
    """

    transaction_id: str
    user_id: str
    amount: float
    currency: str
    timestamp: float  # Unix epoch (UTC)
    merchant_id: str
    merchant_category: str  # MCC code string, e.g. "grocery"
    location: str  # ISO-3166 country code, e.g. "US"
    device_id: str
    ip_address: str
    is_international: bool = False
    is_card_present: bool = True
    channel: str = "online"  # online | pos | atm | mobile

    # ── factory ──────────────────────────────

    @classmethod
    def new(cls, **kwargs) -> "Transaction":
        """Create with auto-generated ID and current timestamp."""
        kwargs.setdefault("transaction_id", str(uuid.uuid4()))
        kwargs.setdefault("timestamp", time.time())
        return cls(**kwargs)

    # ── validation ───────────────────────────

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError(f"Amount must be positive, got {self.amount}")
        if not self.user_id:
            raise ValueError("user_id cannot be empty")
        if not self.transaction_id:
            raise ValueError("transaction_id cannot be empty")

    # ── serialization ────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "currency": self.currency,
            "timestamp": self.timestamp,
            "merchant_id": self.merchant_id,
            "merchant_category": self.merchant_category,
            "location": self.location,
            "device_id": self.device_id,
            "ip_address": self.ip_address,
            "is_international": self.is_international,
            "is_card_present": self.is_card_present,
            "channel": self.channel,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transaction":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ──────────────────────────────────────────────
# Feature Vector
# ──────────────────────────────────────────────


@dataclass
class FeatureVector:
    """
    Engineered features derived from a Transaction + history.
    Used as ML model input — separates feature engineering from detection.
    """

    # Amount features
    amount: float
    amount_log: float
    amount_zscore: float  # deviation from user's own average
    amount_vs_merchant_avg: float  # deviation from merchant's average

    # Velocity features
    txn_count_1h: int  # user's transactions in last 1 hour
    txn_count_24h: int  # user's transactions in last 24 hours
    amount_sum_1h: float  # total spend in last 1 hour
    amount_sum_24h: float  # total spend in last 24 hours

    # Temporal features
    hour_of_day: int  # 0–23
    day_of_week: int  # 0 = Monday
    is_weekend: bool
    is_night: bool  # 00:00–05:59 local

    # Geo / device features
    location_encoded: int
    is_new_location: bool  # first time in this country for user
    is_new_device: bool  # first time this device appears
    device_encoded: int
    ip_encoded: int

    # Merchant features
    merchant_risk_score: float  # 0–1 based on category
    is_high_risk_merchant: bool

    # Graph features
    shared_device_user_count: int  # how many users share this device
    shared_ip_user_count: int  # how many users share this IP
    user_fraud_ring_score: float  # graph-derived ring membership score

    def to_array(self) -> List[float]:
        """Return ordered numeric array for ML model input."""
        return [
            self.amount,
            self.amount_log,
            self.amount_zscore,
            self.amount_vs_merchant_avg,
            float(self.txn_count_1h),
            float(self.txn_count_24h),
            self.amount_sum_1h,
            self.amount_sum_24h,
            float(self.hour_of_day),
            float(self.day_of_week),
            float(self.is_weekend),
            float(self.is_night),
            float(self.location_encoded),
            float(self.is_new_location),
            float(self.is_new_device),
            float(self.device_encoded),
            float(self.ip_encoded),
            self.merchant_risk_score,
            float(self.is_high_risk_merchant),
            float(self.shared_device_user_count),
            float(self.shared_ip_user_count),
            self.user_fraud_ring_score,
        ]

    FEATURE_NAMES = [
        "amount",
        "amount_log",
        "amount_zscore",
        "amount_vs_merchant_avg",
        "txn_count_1h",
        "txn_count_24h",
        "amount_sum_1h",
        "amount_sum_24h",
        "hour_of_day",
        "day_of_week",
        "is_weekend",
        "is_night",
        "location_encoded",
        "is_new_location",
        "is_new_device",
        "device_encoded",
        "ip_encoded",
        "merchant_risk_score",
        "is_high_risk_merchant",
        "shared_device_user_count",
        "shared_ip_user_count",
        "user_fraud_ring_score",
    ]


# ──────────────────────────────────────────────
# Rule Result
# ──────────────────────────────────────────────


@dataclass
class RuleResult:
    """Result from a single rule evaluation."""

    rule_name: str
    triggered: bool
    score: float  # 0.0 – 1.0
    reason: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    # FIX (critical-rule override): when True, this rule represents a
    # deterministic, business-certain fraud signal (e.g. amount exceeds
    # an absolute hard limit). Such signals must force BLOCK regardless
    # of what the ML/graph layers say — a probabilistic average must
    # never be able to water down a 100%-certain rule violation.
    critical: bool = False


# ──────────────────────────────────────────────
# Fraud Result  (final decision)
# ──────────────────────────────────────────────


@dataclass
class FraudResult:
    """
    Complete fraud evaluation result for a transaction.
    Includes ensemble score, decision, SHAP explanation, and audit trail.
    """

    transaction_id: str
    is_fraud: bool
    score: float  # ensemble score 0.0 – 1.0
    risk_level: RiskLevel
    decision: Decision

    # Explanation
    rule_results: List[RuleResult] = field(default_factory=list)
    top_features: List[Dict[str, float]] = field(default_factory=list)  # SHAP
    explanation_text: str = ""

    # Individual model scores for audit
    rule_score: float = 0.0
    ml_score: float = 0.0
    graph_score: float = 0.0

    # Metadata
    latency_ms: float = 0.0
    model_version: str = "1.0.0"
    evaluated_at: float = field(default_factory=time.time)

    # Analyst feedback (populated after review)
    analyst_label: Optional[bool] = None
    analyst_notes: str = ""

    @property
    def primary_reasons(self) -> List[str]:
        return [r.reason for r in self.rule_results if r.triggered]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "is_fraud": self.is_fraud,
            "score": round(self.score, 4),
            "risk_level": self.risk_level.value,
            "decision": self.decision.value,
            "reasons": self.primary_reasons,
            "top_features": self.top_features,
            "explanation": self.explanation_text,
            "scores": {
                "rule": round(self.rule_score, 4),
                "ml": round(self.ml_score, 4),
                "graph": round(self.graph_score, 4),
            },
            "latency_ms": round(self.latency_ms, 2),
            "model_version": self.model_version,
            "evaluated_at": self.evaluated_at,
        }

"""
Feature Engineering Pipeline.
Converts raw Transaction + history into a FeatureVector for ML models.
All features mirror what real fraud teams use (Stripe, PayPal, Razorpay).
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from typing import Dict, List

from .models import FeatureVector, Transaction

logger = logging.getLogger(__name__)

# ── Merchant category risk scores (MCC-based) ──────────────────────────────
MERCHANT_RISK = {
    "gambling": 1.0,
    "crypto": 0.9,
    "wire_transfer": 0.85,
    "jewelry": 0.75,
    "electronics": 0.65,
    "travel": 0.55,
    "restaurant": 0.2,
    "grocery": 0.1,
    "pharmacy": 0.15,
    "utility": 0.05,
    "unknown": 0.5,  # conservative default
}

# ── Location encoding (stable mapping) ────────────────────────────────────
LOCATION_ENCODING: Dict[str, int] = {
    "US": 1,
    "IN": 2,
    "UK": 3,
    "CA": 4,
    "AU": 5,
    "DE": 6,
    "JP": 7,
    "CN": 8,
    "BR": 9,
    "RU": 10,
    "NG": 11,
    "ZA": 12,
    "FR": 13,
    "SG": 14,
    "AE": 15,
}


class FeatureEngineer:
    """
    Stateful feature engineer.
    Maintains per-user and per-merchant history windows for velocity features.
    Thread-safe for single-process use; for multi-process use Redis-backed version.
    """

    # Rolling window sizes (seconds)
    WINDOW_1H = 3_600
    WINDOW_24H = 86_400

    def __init__(self) -> None:
        # user_id → list of (timestamp, amount, location, device_id, ip)
        self._user_history: Dict[str, List] = defaultdict(list)
        # merchant_id → list of amounts
        self._merchant_amounts: Dict[str, List[float]] = defaultdict(list)
        # device_id → set of user_ids
        self._device_users: Dict[str, set] = defaultdict(set)
        # ip → set of user_ids
        self._ip_users: Dict[str, set] = defaultdict(set)

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def extract(self, tx: Transaction, graph_score: float = 0.0) -> FeatureVector:
        """
        Build a FeatureVector for `tx`.
        Call BEFORE calling update() so history doesn't include current tx.
        """
        now = tx.timestamp
        user_hist = self._user_history[tx.user_id]
        self._prune(user_hist, now)

        # ── Amount stats ──────────────────────────────────────────────────
        user_amounts = [h[1] for h in user_hist]
        amount_mean = _mean(user_amounts) if user_amounts else tx.amount
        amount_std = _std(user_amounts) if len(user_amounts) > 1 else 1.0
        amount_zscore = (tx.amount - amount_mean) / max(amount_std, 1.0)
        amount_zscore = max(-10.0, min(float(amount_zscore), 10.0))

        merch_amounts = self._merchant_amounts[tx.merchant_id]
        merch_mean = _mean(merch_amounts) if merch_amounts else tx.amount
        merch_std = _std(merch_amounts) if len(merch_amounts) > 1 else 1.0
        amount_vs_merchant = (tx.amount - merch_mean) / max(merch_std, 1.0)
        amount_vs_merchant = max(-10.0, min(float(amount_vs_merchant), 10.0))

        # ── Velocity ──────────────────────────────────────────────────────
        hist_1h = [h for h in user_hist if now - h[0] <= self.WINDOW_1H]
        hist_24h = [h for h in user_hist if now - h[0] <= self.WINDOW_24H]

        # ── Temporal ──────────────────────────────────────────────────────
        import datetime

        dt = datetime.datetime.fromtimestamp(now, datetime.timezone.utc)
        hour = dt.hour
        dow = dt.weekday()  # 0=Monday
        is_weekend = dow >= 5
        is_night = hour < 6

        # ── Geo / device ──────────────────────────────────────────────────
        seen_locations = {h[2] for h in user_hist}
        seen_devices = {h[3] for h in user_hist}
        is_new_location = tx.location not in seen_locations
        is_new_device = tx.device_id not in seen_devices

        loc_enc = LOCATION_ENCODING.get(tx.location, 99)
        device_enc = hash(tx.device_id) % 10_000
        ip_enc = hash(tx.ip_address) % 10_000

        # ── Merchant risk ─────────────────────────────────────────────────
        merch_risk = MERCHANT_RISK.get(tx.merchant_category.lower(), MERCHANT_RISK["unknown"])
        high_risk_m = merch_risk >= 0.7

        # ── Graph features ────────────────────────────────────────────────
        shared_device = len(self._device_users.get(tx.device_id, set()))
        shared_ip = len(self._ip_users.get(tx.ip_address, set()))

        return FeatureVector(
            amount=tx.amount,
            amount_log=math.log1p(tx.amount),
            amount_zscore=float(amount_zscore),
            amount_vs_merchant_avg=float(amount_vs_merchant),
            txn_count_1h=len(hist_1h),
            txn_count_24h=len(hist_24h),
            amount_sum_1h=sum(h[1] for h in hist_1h),
            amount_sum_24h=sum(h[1] for h in hist_24h),
            hour_of_day=hour,
            day_of_week=dow,
            is_weekend=is_weekend,
            is_night=is_night,
            location_encoded=loc_enc,
            is_new_location=is_new_location,
            is_new_device=is_new_device,
            device_encoded=device_enc,
            ip_encoded=ip_enc,
            merchant_risk_score=merch_risk,
            is_high_risk_merchant=high_risk_m,
            shared_device_user_count=shared_device,
            shared_ip_user_count=shared_ip,
            user_fraud_ring_score=graph_score,
        )

    def update(self, tx: Transaction) -> None:
        """
        Update history with the current transaction.
        Always call AFTER extract() to avoid data leakage.
        """
        self._user_history[tx.user_id].append(
            (tx.timestamp, tx.amount, tx.location, tx.device_id, tx.ip_address)
        )
        self._merchant_amounts[tx.merchant_id].append(tx.amount)
        # cap merchant history at 500 entries
        if len(self._merchant_amounts[tx.merchant_id]) > 500:
            self._merchant_amounts[tx.merchant_id].pop(0)

        self._device_users[tx.device_id].add(tx.user_id)
        self._ip_users[tx.ip_address].add(tx.user_id)

    def get_user_stats(self, user_id: str) -> Dict:
        """Summary stats for a user — used in dashboard."""
        hist = self._user_history[user_id]
        amounts = [h[1] for h in hist]
        return {
            "total_transactions": len(hist),
            "avg_amount": round(_mean(amounts), 2) if amounts else 0,
            "max_amount": round(max(amounts), 2) if amounts else 0,
            "countries": list({h[2] for h in hist}),
        }

    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────

    def _prune(self, history: List, now: float) -> None:
        """Remove entries older than 24h to bound memory growth."""
        cutoff = now - self.WINDOW_24H
        while history and history[0][0] < cutoff:
            history.pop(0)


# ── Math helpers ────────────────────────────────────────────────────────────


def _mean(vals: List[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: List[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))

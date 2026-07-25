"""
IEEE-CIS Feature Mapper
Converts raw IEEE-CIS Kaggle dataset columns → our 22-feature FeatureVector.

IEEE-CIS dataset has 590k real Vesta Corporation transactions.
Columns we use:
  TransactionAmt, ProductCD, card4, card6, P_emaildomain,
  R_emaildomain, addr1, addr2, dist1, dist2,
  C1-C14 (counts), D1-D15 (time deltas),
  V1-V339 (Vesta engineered features — we use top ones),
  isFraud (target label)
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Merchant category mapping from ProductCD ──────────────────────────────
PRODUCT_RISK = {
    "W": 0.1,   # physical goods
    "H": 0.3,   # hotel/travel
    "C": 0.6,   # electronic check
    "S": 0.4,   # services
    "R": 0.5,   # crypto/digital
}

# ── High risk email domains ───────────────────────────────────────────────
HIGH_RISK_DOMAINS = {
    "protonmail.com", "guerrillamail.com", "temp-mail.org",
    "mailnull.com", "yopmail.com", "throwam.com",
}


def map_ieee_to_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Map IEEE-CIS columns to our 22 FeatureVector fields.
    Returns a DataFrame with exactly our feature names.
    """
    logger.info("Mapping %d rows from IEEE-CIS format...", len(df))
    out = pd.DataFrame()

    # ── Amount features ───────────────────────────────────────────────────
    out["amount"]                 = df["TransactionAmt"].fillna(0)
    out["amount_log"]             = np.log1p(out["amount"])
    # Z-score using C5 (count of transactions with same amount)
    out["amount_zscore"]          = df.get("V258", pd.Series(0, index=df.index)).fillna(0)
    out["amount_vs_merchant_avg"] = df.get("V257", pd.Series(0, index=df.index)).fillna(0)

    # ── Velocity features (C columns = counts) ────────────────────────────
    out["txn_count_1h"]   = df.get("C1",  pd.Series(1, index=df.index)).fillna(1)
    out["txn_count_24h"]  = df.get("C2",  pd.Series(1, index=df.index)).fillna(1)
    out["amount_sum_1h"]  = out["amount"] * out["txn_count_1h"]
    out["amount_sum_24h"] = out["amount"] * out["txn_count_24h"]

    # ── Temporal features (D1 = days since last transaction) ──────────────
    # TransactionDT is seconds since reference — derive hour and day
    if "TransactionDT" in df.columns:
        dt_hours             = (df["TransactionDT"] / 3600).fillna(0)
        out["hour_of_day"]   = (dt_hours % 24).astype(int)
        out["day_of_week"]   = ((dt_hours / 24) % 7).astype(int)
        out["is_weekend"]    = (out["day_of_week"] >= 5).astype(float)
        out["is_night"]      = (out["hour_of_day"] < 6).astype(float)
    else:
        out["hour_of_day"]  = 12
        out["day_of_week"]  = 1
        out["is_weekend"]   = 0.0
        out["is_night"]     = 0.0

    # ── Geo / device features ─────────────────────────────────────────────
    # addr1 = billing zip, addr2 = billing country
    out["location_encoded"] = df.get("addr2", pd.Series(0, index=df.index)).fillna(0)
    # D11 = days since account open (0 = new account)
    d11                      = df.get("D11", pd.Series(30, index=df.index)).fillna(30)
    out["is_new_location"]   = (d11 < 1).astype(float)
    out["is_new_device"]     = (df.get("D6", pd.Series(1, index=df.index)).fillna(1) < 1).astype(float)
    # card1 encoded as device proxy
    out["device_encoded"]    = df.get("card1", pd.Series(0, index=df.index)).fillna(0)
    out["ip_encoded"]        = df.get("addr1", pd.Series(0, index=df.index)).fillna(0)

    # ── Merchant risk (ProductCD) ──────────────────────────────────────────
    out["merchant_risk_score"] = df.get("ProductCD", pd.Series("W", index=df.index)) \
                                   .map(PRODUCT_RISK).fillna(0.3)
    out["is_high_risk_merchant"] = (out["merchant_risk_score"] >= 0.6).astype(float)

    # ── Graph features (C columns proxy) ──────────────────────────────────
    # C13 = count of addresses associated with card
    out["shared_device_user_count"] = df.get("C13", pd.Series(1, index=df.index)).fillna(1)
    # C11 = count of cards per address
    out["shared_ip_user_count"]     = df.get("C11", pd.Series(1, index=df.index)).fillna(1)
    # V258 reused as ring score proxy
    out["user_fraud_ring_score"]    = np.clip(
        df.get("V258", pd.Series(0, index=df.index)).fillna(0) / 10.0, 0, 1
    )

    # ── Clip all values to reasonable ranges ──────────────────────────────
    out["txn_count_1h"]             = out["txn_count_1h"].clip(0, 500)
    out["txn_count_24h"]            = out["txn_count_24h"].clip(0, 1000)
    out["shared_device_user_count"] = out["shared_device_user_count"].clip(0, 100)
    out["shared_ip_user_count"]     = out["shared_ip_user_count"].clip(0, 100)
    out["amount_zscore"]            = out["amount_zscore"].clip(-10, 10)

    logger.info("Feature mapping complete. Shape: %s", out.shape)
    return out


FEATURE_NAMES = [
    "amount", "amount_log", "amount_zscore", "amount_vs_merchant_avg",
    "txn_count_1h", "txn_count_24h", "amount_sum_1h", "amount_sum_24h",
    "hour_of_day", "day_of_week", "is_weekend", "is_night",
    "location_encoded", "is_new_location", "is_new_device",
    "device_encoded", "ip_encoded",
    "merchant_risk_score", "is_high_risk_merchant",
    "shared_device_user_count", "shared_ip_user_count",
    "user_fraud_ring_score",
]

assert len(FEATURE_NAMES) == 22, f"Expected 22 features, got {len(FEATURE_NAMES)}"

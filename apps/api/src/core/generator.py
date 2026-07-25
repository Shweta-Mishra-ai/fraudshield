"""
Realistic Transaction Generator for demo/testing.
Simulates legitimate users + 6 real-world fraud patterns:
  1. High-value account takeover
  2. Card testing (many small transactions)
  3. Velocity burst (rapid fire)
  4. New device + new location combo
  5. Shared device fraud ring
  6. Night-time crypto merchant
"""

from __future__ import annotations

import random
import time
import uuid
from typing import Generator, List

from .models import Transaction

# ── Realistic merchant categories ──────────────────────────────────────────
MERCHANT_CATEGORIES = [
    ("grocery",      0.40),
    ("restaurant",   0.20),
    ("electronics",  0.10),
    ("travel",       0.08),
    ("pharmacy",     0.07),
    ("utility",      0.05),
    ("jewelry",      0.04),
    ("crypto",       0.03),
    ("gambling",     0.02),
    ("wire_transfer", 0.01),
]

LOCATIONS = ["US", "IN", "UK", "CA", "AU", "DE", "JP", "SG", "AE", "BR"]

def _weighted_category() -> str:
    cats, weights = zip(*MERCHANT_CATEGORIES)
    return random.choices(cats, weights=weights, k=1)[0]


class TransactionGenerator:
    """
    Generates a realistic mix of legitimate + fraudulent transactions.
    Fraud rate is approximately 5% by default.
    """

    FRAUD_RATE = 0.05

    def __init__(self, n_users: int = 100, n_merchants: int = 30) -> None:
        self.users     = [f"USER_{i:04d}" for i in range(1, n_users + 1)]
        self.merchants = [f"MERCH_{i:03d}" for i in range(1, n_merchants + 1)]
        self.devices   = [f"DEV_{i:04d}" for i in range(1, 200)]
        # Assign users a "home" location and device for realism
        self._user_home_loc    = {u: random.choice(LOCATIONS[:5]) for u in self.users}
        self._user_home_device = {u: random.choice(self.devices[:100]) for u in self.users}
        # Shared ring devices (for fraud ring simulation)
        self._ring_devices = [f"RING_DEV_{i}" for i in range(3)]
        self._ring_ip      = "10.0.0.99"

    def generate_stream(self, delay: float = 0.3) -> Generator[Transaction, None, None]:
        """
        Infinite generator. Yields one transaction every `delay` seconds.
        Mix: ~95% legitimate, ~5% fraud scenarios.
        """
        while True:
            roll = random.random()
            if roll < self.FRAUD_RATE:
                tx = self._fraud_transaction()
            else:
                tx = self._normal_transaction()
            yield tx
            time.sleep(delay * random.uniform(0.5, 1.5))

    def generate_batch(self, n: int = 200) -> List[Transaction]:
        """Generate a fixed batch — useful for testing and model training."""
        txns = []
        for _ in range(n):
            roll = random.random()
            txns.append(self._fraud_transaction() if roll < self.FRAUD_RATE else self._normal_transaction())
        return txns

    # ──────────────────────────────────────────────────────────────────────
    # Normal transaction
    # ──────────────────────────────────────────────────────────────────────

    def _normal_transaction(self) -> Transaction:
        user     = random.choice(self.users)
        category = _weighted_category()
        merchant = random.choice(self.merchants)

        # Most transactions: user's home location and home device
        loc    = self._user_home_loc[user] if random.random() > 0.1 else random.choice(LOCATIONS)
        device = self._user_home_device[user] if random.random() > 0.05 else random.choice(self.devices)

        # Amount distribution realistic by category
        amount_ranges = {
            "grocery": (20, 200), "restaurant": (15, 120),
            "electronics": (50, 800), "travel": (200, 2000),
            "pharmacy": (10, 150), "utility": (50, 300),
            "jewelry": (100, 2000), "crypto": (50, 500),
            "gambling": (20, 500), "wire_transfer": (500, 5000),
        }
        lo, hi = amount_ranges.get(category, (10, 500))
        amount = round(random.uniform(lo, hi), 2)

        return Transaction(
            transaction_id   = str(uuid.uuid4()),
            user_id          = user,
            amount           = amount,
            currency         = "USD",
            timestamp        = time.time(),
            merchant_id      = merchant,
            merchant_category = category,
            location         = loc,
            device_id        = device,
            ip_address       = f"192.168.{random.randint(1,254)}.{random.randint(1,254)}",
            is_international = loc != self._user_home_loc[user],
            channel          = random.choice(["online", "mobile", "pos"]),
        )

    # ──────────────────────────────────────────────────────────────────────
    # Fraud scenarios
    # ──────────────────────────────────────────────────────────────────────

    def _fraud_transaction(self) -> Transaction:
        scenario = random.choices(
            ["high_value_ato", "card_testing", "velocity_burst",
             "new_device_new_loc", "ring_device", "night_crypto"],
            weights=[0.25, 0.20, 0.20, 0.15, 0.10, 0.10],
            k=1,
        )[0]

        user = random.choice(self.users)
        base = dict(
            transaction_id   = str(uuid.uuid4()),
            user_id          = user,
            currency         = "USD",
            timestamp        = time.time(),
            merchant_id      = random.choice(self.merchants),
            merchant_category = _weighted_category(),
            location         = self._user_home_loc[user],
            device_id        = self._user_home_device[user],
            ip_address       = f"192.168.{random.randint(1,254)}.{random.randint(1,254)}",
            is_international = False,
            channel          = "online",
        )

        if scenario == "high_value_ato":
            # Account takeover: large amount, different device
            base.update(amount=round(random.uniform(8000, 25000), 2),
                        device_id=f"UNKNOWN_{uuid.uuid4().hex[:6]}",
                        merchant_category="electronics")

        elif scenario == "card_testing":
            # Card testing: small amounts on high-risk merchant
            base.update(amount=round(random.uniform(1.00, 9.99), 2),
                        merchant_category="crypto")

        elif scenario == "velocity_burst":
            # Rapid spending on travel
            base.update(amount=round(random.uniform(200, 800), 2),
                        merchant_category="travel")

        elif scenario == "new_device_new_loc":
            # Impossible travel: new device + foreign country
            foreign = random.choice([loc for loc in LOCATIONS if loc != self._user_home_loc[user]])
            base.update(amount=round(random.uniform(500, 3000), 2),
                        location=foreign,
                        device_id=f"FOREIGN_{uuid.uuid4().hex[:6]}",
                        is_international=True)

        elif scenario == "ring_device":
            # Fraud ring: shared device
            base.update(amount=round(random.uniform(100, 2000), 2),
                        device_id=random.choice(self._ring_devices),
                        ip_address=self._ring_ip,
                        merchant_category="jewelry")

        elif scenario == "night_crypto":
            # Night-time crypto transaction
            import datetime
            # Force 2am UTC
            dt  = datetime.datetime.now(datetime.timezone.utc).replace(hour=2, minute=random.randint(0,59))
            base.update(amount=round(random.uniform(1000, 5000), 2),
                        merchant_category="crypto",
                        timestamp=dt.timestamp())

        return Transaction(**base)

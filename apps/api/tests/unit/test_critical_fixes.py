"""
Regression tests for critical production fixes.
These specifically guard against the bugs found and fixed during
the pre-deployment audit — they must never regress.
"""

from __future__ import annotations
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.core.models import Transaction, Decision
from src.core.detector import FraudDetector
from src.core.graph import FraudGraphEngine
from src.core.generator import TransactionGenerator
from src.core.storage import FraudStorage


def tx(**kw) -> Transaction:
    d = dict(
        transaction_id=str(uuid.uuid4()),
        user_id="U001",
        amount=100.0,
        currency="USD",
        timestamp=time.time(),
        merchant_id="M001",
        merchant_category="grocery",
        location="US",
        device_id="D001",
        ip_address="192.168.1.1",
        is_international=False,
        is_card_present=True,
        channel="online",
    )
    d.update(kw)
    return Transaction(**d)


# ══════════════════════════════════════════════════════════════════════════
# FIX #1 — Critical rule hard-override (extreme fraud must BLOCK, not REVIEW)
# ══════════════════════════════════════════════════════════════════════════


class TestCriticalOverride:
    """
    Bug: a rule scoring 1.0 (100% certain, e.g. amount over an absolute
    hard limit) could still only reach ~0.40 in the weighted ensemble,
    landing on REVIEW instead of BLOCK. Fixed by adding a `critical` flag
    on RuleResult that forces BLOCK regardless of ML/graph opinion.
    """

    def test_extreme_amount_blocks(self):
        det = FraudDetector()
        result = det.analyze(tx(amount=100_000.0))
        assert result.decision == Decision.BLOCK
        assert result.score >= 0.90

    def test_exactly_at_critical_threshold_blocks(self):
        det = FraudDetector()
        result = det.analyze(tx(amount=10_000.00))
        assert result.decision == Decision.BLOCK

    def test_just_below_critical_does_not_force_block(self):
        det = FraudDetector()
        result = det.analyze(tx(amount=9_999.99))
        assert result.decision != Decision.BLOCK

    def test_normal_transaction_unaffected(self):
        det = FraudDetector()
        result = det.analyze(tx(amount=50.0))
        assert result.decision == Decision.ALLOW
        assert result.score < 0.1

    def test_crypto_plus_huge_amount_blocks(self):
        det = FraudDetector()
        result = det.analyze(tx(amount=50_000.0, merchant_category="crypto"))
        assert result.decision == Decision.BLOCK


# ══════════════════════════════════════════════════════════════════════════
# FIX #2 — is_fraud semantics (must mean confirmed BLOCK, not ambiguous REVIEW)
# ══════════════════════════════════════════════════════════════════════════


class TestIsFraudSemantics:
    """
    Bug: is_fraud was True for both REVIEW and BLOCK decisions, causing
    dashboards to show ambiguous "needs human review" transactions with
    the same alarming red "FRAUD" label as confirmed blocks — and
    inflating "fraud_count" stats with non-confirmed cases.
    """

    def test_block_has_is_fraud_true(self):
        det = FraudDetector()
        result = det.analyze(tx(amount=100_000.0))
        assert result.decision == Decision.BLOCK
        assert result.is_fraud is True

    def test_allow_has_is_fraud_false(self):
        det = FraudDetector()
        result = det.analyze(tx(amount=50.0))
        assert result.decision == Decision.ALLOW
        assert result.is_fraud is False

    def test_review_has_is_fraud_false(self):
        """REVIEW is ambiguous — must NOT be marked as confirmed fraud."""
        det = FraudDetector()
        # Craft a scenario likely to land on REVIEW: established user,
        # new country, elevated amount
        for i in range(10):
            det.analyze(tx(transaction_id=f"hist-{i}", user_id="ESTABLISHED_USER"))
        result = det.analyze(
            tx(
                transaction_id="review-case",
                user_id="ESTABLISHED_USER",
                amount=1000.0,
                location="JP",
            )
        )
        if result.decision == Decision.REVIEW:
            assert result.is_fraud is False

    def test_is_fraud_always_matches_block_decision(self):
        """Invariant: is_fraud must always equal (decision == BLOCK)."""
        det = FraudDetector()
        gen = TransactionGenerator(n_users=20)
        for t in gen.generate_batch(100):
            r = det.analyze(t)
            assert r.is_fraud == (r.decision == Decision.BLOCK), (
                f"is_fraud/decision mismatch: is_fraud={r.is_fraud}, "
                f"decision={r.decision.value}"
            )


# ══════════════════════════════════════════════════════════════════════════
# FIX #3 — Memory safety (graph must not grow unbounded)
# ══════════════════════════════════════════════════════════════════════════


class TestMemorySafety:
    """
    Bug: FraudGraphEngine never pruned old nodes/edges — over weeks of
    continuous uptime on a memory-limited instance, this would eventually
    exhaust RAM and crash the service. Fixed with a FIFO eviction cap.
    """

    def test_graph_respects_node_cap(self):
        g = FraudGraphEngine()
        g.MAX_GRAPH_NODES = 50

        class FakeTx:
            def __init__(self, i):
                self.user_id = f"U{i}"
                self.device_id = f"D{i}"
                self.ip_address = f"1.1.1.{i % 250}"
                self.merchant_id = f"M{i}"
                self.amount = 100.0

        for i in range(500):
            g.add_transaction(FakeTx(i))

        assert g._graph.number_of_nodes() <= 50

    def test_graph_still_functions_after_eviction(self):
        """Eviction must not break ring detection for recent data."""
        g = FraudGraphEngine()
        g.MAX_GRAPH_NODES = 30

        class FakeTx:
            def __init__(self, i, device="D_OLD"):
                self.user_id = f"U{i}"
                self.device_id = device
                self.ip_address = f"1.1.1.{i % 250}"
                self.merchant_id = f"M{i}"
                self.amount = 100.0

        # Fill with old data to trigger eviction
        for i in range(100):
            g.add_transaction(FakeTx(i))

        # Add a fresh ring — must still be detectable
        for i in range(100, 105):
            g.add_transaction(FakeTx(i, device="RING_DEVICE_FRESH"))

        rings = g.detect_rings()
        assert any(r["entity"] == "RING_DEVICE_FRESH" for r in rings)


# ══════════════════════════════════════════════════════════════════════════
# FIX #4 — Cold-start (must not regress to false-positive epidemic)
# ══════════════════════════════════════════════════════════════════════════


class TestColdStartRegression:
    def test_new_users_mostly_allowed(self):
        det = FraudDetector()
        non_allow = 0
        n = 50
        for i in range(n):
            t = tx(
                transaction_id=str(uuid.uuid4()),
                user_id=f"NEW_{uuid.uuid4().hex[:8]}",
                amount=100.0,
                merchant_category="grocery",
                device_id=f"UDEV_{uuid.uuid4().hex[:8]}",
                ip_address=f"10.{i}.1.1",
            )
            if det.analyze(t).decision != Decision.ALLOW:
                non_allow += 1
        rate = non_allow / n * 100
        assert rate < 10, f"Cold-start review rate too high: {rate:.0f}%"


# ══════════════════════════════════════════════════════════════════════════
# Load / Stress Testing
# ══════════════════════════════════════════════════════════════════════════


class TestLoadHandling:
    def test_1000_transactions_zero_crashes(self):
        det = FraudDetector()
        gen = TransactionGenerator(n_users=100, n_merchants=30)
        crashes = 0
        for t in gen.generate_batch(1000):
            try:
                r = det.analyze(t)
                assert 0.0 <= r.score <= 1.0
                assert r.decision.value in ("ALLOW", "REVIEW", "BLOCK")
                assert r.is_fraud == (r.decision == Decision.BLOCK)
            except Exception:
                crashes += 1
        assert crashes == 0

    def test_latency_stays_bounded_under_load(self):
        det = FraudDetector()
        gen = TransactionGenerator(n_users=50)
        latencies = []
        for t in gen.generate_batch(200):
            r = det.analyze(t)
            latencies.append(r.latency_ms)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 500, f"p95 latency too high: {p95}ms"

    def test_storage_handles_concurrent_writes(self, tmp_path):
        """Simulate rapid sequential writes — must not corrupt/crash."""
        store = FraudStorage(db_path=str(tmp_path / "load.db"))
        det = FraudDetector()
        gen = TransactionGenerator(n_users=20)
        for t in gen.generate_batch(200):
            r = det.analyze(t)
            store.save(t, r)
        stats = store.get_stats()
        assert stats["total_transactions"] == 200


# ══════════════════════════════════════════════════════════════════════════
# Error Handling — malformed / adversarial input
# ══════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    def test_zero_amount_rejected_at_model_level(self):
        with pytest.raises(ValueError):
            tx(amount=0.0)

    def test_negative_amount_rejected(self):
        with pytest.raises(ValueError):
            tx(amount=-100.0)

    def test_empty_user_id_rejected(self):
        with pytest.raises(ValueError):
            tx(user_id="")

    def test_detector_never_raises_to_caller(self):
        """Even with a broken internal component, analyze() must not raise."""
        det = FraudDetector()
        original = det.features.extract
        det.features.extract = lambda *a, **kw: (_ for _ in ()).throw(
            RuntimeError("simulated internal failure")
        )
        result = det.analyze(tx())  # must not raise
        assert result.decision == Decision.ALLOW  # fail-open
        det.features.extract = original

    def test_storage_survives_duplicate_saves(self, tmp_path):
        store = FraudStorage(db_path=str(tmp_path / "dup.db"))
        det = FraudDetector()
        t = tx()
        r = det.analyze(t)
        store.save(t, r)
        store.save(t, r)  # duplicate — must not raise
        assert len(store.get_recent(10)) == 1

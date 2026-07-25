"""Integration tests — storage, streaming pipeline, end-to-end flow."""

from __future__ import annotations
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from src.core.models import Transaction, FraudResult, RiskLevel, Decision
from src.core.storage import FraudStorage
from src.core.detector import FraudDetector
from src.core.generator import TransactionGenerator
from src.streaming.pathway_pipeline import write_transactions_to_csv


def tx(**kw) -> Transaction:
    d = dict(
        transaction_id="tx-001",
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


# ── Storage ───────────────────────────────────────────────────────────────


class TestFraudStorage:
    @pytest.fixture(autouse=True)
    def tmp_db(self, tmp_path):
        self.store = FraudStorage(db_path=str(tmp_path / "test.db"))

    def _result(
        self, t: Transaction, fraud=False, score=0.1, decision=Decision.ALLOW, risk=RiskLevel.LOW
    ) -> FraudResult:
        return FraudResult(
            transaction_id=t.transaction_id,
            is_fraud=fraud,
            score=score,
            risk_level=risk,
            decision=decision,
            model_version="test",
            evaluated_at=time.time(),
        )

    def test_save_and_retrieve(self):
        t = tx()
        self.store.save(t, self._result(t))
        rows = self.store.get_recent(10)
        assert len(rows) == 1 and rows[0]["id"] == t.transaction_id

    def test_stats_correct(self):
        t = tx()
        self.store.save(t, self._result(t))
        s = self.store.get_stats()
        assert s["total_transactions"] == 1
        assert s["fraud_count"] == 0
        assert s["fraud_rate"] == 0.0

    def test_fraud_stats(self):
        t = tx()
        self.store.save(
            t,
            self._result(
                t, fraud=True, score=0.9, decision=Decision.BLOCK, risk=RiskLevel.CRITICAL
            ),
        )
        s = self.store.get_stats()
        assert s["fraud_count"] == 1
        assert s["blocked_count"] == 1

    def test_analyst_review_removes_from_alerts(self):
        t = tx()
        self.store.save(
            t,
            self._result(
                t, fraud=True, score=0.9, decision=Decision.BLOCK, risk=RiskLevel.CRITICAL
            ),
        )
        alerts_before = self.store.get_alerts(10)
        assert any(a["id"] == t.transaction_id for a in alerts_before)

        self.store.update_analyst_review(t.transaction_id, False, "False positive")
        alerts_after = self.store.get_alerts(10)
        assert not any(a["id"] == t.transaction_id for a in alerts_after)

    def test_idempotent_save(self):
        t = tx()
        r = self._result(t)
        self.store.save(t, r)
        self.store.save(t, r)
        assert len(self.store.get_recent(10)) == 1

    def test_user_history(self):
        for i in range(5):
            t = tx(transaction_id=f"tx-{i}")
            self.store.save(t, self._result(t))
        hist = self.store.get_user_history("U001", 10)
        assert len(hist) == 5

    def test_alerts_ordered_by_score_desc(self):
        for i, score in enumerate([0.5, 0.9, 0.7]):
            t = tx(transaction_id=f"tx-{i}")
            r = self._result(
                t, fraud=True, score=score, decision=Decision.REVIEW, risk=RiskLevel.HIGH
            )
            self.store.save(t, r)
        alerts = self.store.get_alerts(10)
        scores = [a["score"] for a in alerts]
        assert scores == sorted(scores, reverse=True)

    def test_get_all_transactions_for_hydration(self):
        for i in range(3):
            t = tx(transaction_id=f"tx-{i}")
            self.store.save(t, self._result(t))
        txns = self.store.get_all_transactions()
        assert len(txns) == 3
        assert all(isinstance(t, Transaction) for t in txns)

    def test_pending_review_count(self):
        for i in range(3):
            t = tx(transaction_id=f"tx-{i}")
            r = self._result(
                t, fraud=True, score=0.9, decision=Decision.BLOCK, risk=RiskLevel.CRITICAL
            )
            self.store.save(t, r)
        s = self.store.get_stats()
        assert s["pending_review"] == 3


# ── End-to-End Flow ───────────────────────────────────────────────────────


class TestEndToEndFlow:
    def test_generate_analyze_store_retrieve(self, tmp_path):
        store = FraudStorage(db_path=str(tmp_path / "e2e.db"))
        det = FraudDetector()
        gen = TransactionGenerator(n_users=10)
        txns = gen.generate_batch(20)

        for t in txns:
            result = det.analyze(t)
            store.save(t, result)

        stats = store.get_stats()
        assert stats["total_transactions"] == 20
        assert stats["fraud_count"] >= 0

        recent = store.get_recent(20)
        assert len(recent) == 20
        for row in recent:
            assert 0.0 <= row["score"] <= 1.0
            assert row["decision"] in ("ALLOW", "REVIEW", "BLOCK")

    def test_fraud_ring_detected_in_flow(self, tmp_path):
        store = FraudStorage(db_path=str(tmp_path / "ring.db"))
        det = FraudDetector()

        ring_device = "RING_DEV_999"
        for i in range(5):
            t = tx(transaction_id=f"ring-{i}", user_id=f"U{i}", device_id=ring_device, amount=500.0)
            result = det.analyze(t)
            store.save(t, result)

        rings = det.graph.detect_rings()
        device_rings = [r for r in rings if r["entity"] == ring_device]
        assert len(device_rings) > 0
        assert device_rings[0]["user_count"] == 5

    def test_hydration_restores_state(self, tmp_path):
        store = FraudStorage(db_path=str(tmp_path / "hyd.db"))
        det1 = FraudDetector()
        gen = TransactionGenerator(n_users=5)

        for t in gen.generate_batch(10):
            result = det1.analyze(t)
            store.save(t, result)

        # New detector hydrated from DB
        det2 = FraudDetector()
        txns = store.get_all_transactions()
        det2.hydrate(txns)
        assert det2._total_analyzed == 10

    def test_high_risk_ends_in_alert_queue(self, tmp_path):
        store = FraudStorage(db_path=str(tmp_path / "alert.db"))
        det = FraudDetector()

        # Guaranteed high-risk: 15k crypto transaction
        t = tx(
            transaction_id="high-risk-001",
            amount=15000.0,
            merchant_category="crypto",
            location="RU",
            is_international=True,
        )
        result = det.analyze(t)
        store.save(t, result)

        if result.decision.value in ("REVIEW", "BLOCK"):
            alerts = store.get_alerts(10)
            assert any(a["id"] == "high-risk-001" for a in alerts)


# ── Pathway CSV Writer ────────────────────────────────────────────────────


class TestPathwayCSVWriter:
    def test_writes_valid_csv(self, tmp_path):
        gen = TransactionGenerator()
        txns = gen.generate_batch(5)
        fname = write_transactions_to_csv(txns, str(tmp_path))
        assert os.path.exists(fname)

    def test_csv_has_correct_rows(self, tmp_path):
        import csv

        gen = TransactionGenerator()
        txns = gen.generate_batch(5)
        fname = write_transactions_to_csv(txns, str(tmp_path))
        with open(fname) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 5

    def test_csv_has_all_fields(self, tmp_path):
        import csv

        gen = TransactionGenerator()
        txns = gen.generate_batch(1)
        fname = write_transactions_to_csv(txns, str(tmp_path))
        with open(fname) as f:
            reader = csv.DictReader(f)
            row = next(reader)
        required = [
            "transaction_id",
            "user_id",
            "amount",
            "currency",
            "merchant_id",
            "location",
            "device_id",
            "ip_address",
        ]
        for field in required:
            assert field in row

    def test_amounts_positive_in_csv(self, tmp_path):
        import csv

        gen = TransactionGenerator()
        txns = gen.generate_batch(10)
        fname = write_transactions_to_csv(txns, str(tmp_path))
        with open(fname) as f:
            rows = list(csv.DictReader(f))
        assert all(float(r["amount"]) > 0 for r in rows)

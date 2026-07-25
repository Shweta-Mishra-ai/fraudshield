"""Unit tests — core components."""

from __future__ import annotations
import math
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from src.core.models import Transaction, RiskLevel, Decision, FeatureVector
from src.core.features import FeatureEngineer, _mean, _std
from src.core.rules import RuleEngine, HighAmountRule, VelocityRule, NewDeviceRule
from src.core.graph import FraudGraphEngine
from src.core.generator import TransactionGenerator
from src.core.detector import FraudDetector


# ── Fixtures ──────────────────────────────────────────────────────────────


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


def fv(**kw) -> FeatureVector:
    d = dict(
        amount=100.0,
        amount_log=math.log1p(100),
        amount_zscore=0.5,
        amount_vs_merchant_avg=0.2,
        txn_count_1h=2,
        txn_count_24h=5,
        amount_sum_1h=200.0,
        amount_sum_24h=500.0,
        hour_of_day=14,
        day_of_week=1,
        is_weekend=False,
        is_night=False,
        location_encoded=1,
        is_new_location=False,
        is_new_device=False,
        device_encoded=1234,
        ip_encoded=5678,
        merchant_risk_score=0.1,
        is_high_risk_merchant=False,
        shared_device_user_count=1,
        shared_ip_user_count=1,
        user_fraud_ring_score=0.0,
    )
    d.update(kw)
    return FeatureVector(**d)


# ── Transaction Model ─────────────────────────────────────────────────────


class TestTransaction:
    def test_valid_creation(self):
        t = tx()
        assert t.amount == 100.0

    def test_negative_amount_raises(self):
        with pytest.raises(ValueError, match="positive"):
            tx(amount=-1.0)

    def test_zero_amount_raises(self):
        with pytest.raises(ValueError):
            tx(amount=0.0)

    def test_empty_user_id_raises(self):
        with pytest.raises(ValueError, match="user_id"):
            tx(user_id="")

    def test_serialization_round_trip(self):
        t = tx()
        t2 = Transaction.from_dict(t.to_dict())
        assert t.transaction_id == t2.transaction_id
        assert t.amount == t2.amount

    def test_new_factory_generates_id(self):
        t = Transaction.new(
            user_id="U",
            amount=50.0,
            currency="USD",
            merchant_id="M",
            merchant_category="grocery",
            location="US",
            device_id="D",
            ip_address="1.2.3.4",
        )
        assert t.transaction_id != "" and t.timestamp > 0

    def test_very_large_amount_allowed(self):
        t = tx(amount=9_999_999.99)
        assert t.amount > 0

    def test_to_dict_contains_all_fields(self):
        d = tx().to_dict()
        for key in [
            "transaction_id",
            "user_id",
            "amount",
            "currency",
            "location",
            "device_id",
            "ip_address",
            "channel",
        ]:
            assert key in d


# ── Enums ─────────────────────────────────────────────────────────────────


class TestEnums:
    def test_risk_critical(self):
        assert RiskLevel.from_score(0.90) == RiskLevel.CRITICAL

    def test_risk_high(self):
        assert RiskLevel.from_score(0.70) == RiskLevel.HIGH

    def test_risk_medium(self):
        assert RiskLevel.from_score(0.50) == RiskLevel.MEDIUM

    def test_risk_low(self):
        assert RiskLevel.from_score(0.10) == RiskLevel.LOW

    def test_risk_boundary_85(self):
        assert RiskLevel.from_score(0.85) == RiskLevel.CRITICAL

    def test_risk_boundary_65(self):
        assert RiskLevel.from_score(0.65) == RiskLevel.HIGH

    def test_decision_block(self):
        assert Decision.from_score(0.85) == Decision.BLOCK

    def test_decision_review(self):
        assert Decision.from_score(0.55) == Decision.REVIEW

    def test_decision_allow(self):
        assert Decision.from_score(0.20) == Decision.ALLOW

    def test_decision_boundary(self):
        assert Decision.from_score(0.80) == Decision.BLOCK


# ── Feature Engineering ───────────────────────────────────────────────────


class TestFeatureEngineer:
    def setup_method(self):
        self.eng = FeatureEngineer()

    def test_first_tx_zero_velocity(self):
        f = self.eng.extract(tx())
        assert f.txn_count_1h == 0 and f.txn_count_24h == 0

    def test_first_tx_new_device(self):
        f = self.eng.extract(tx())
        assert f.is_new_device is True

    def test_first_tx_new_location(self):
        f = self.eng.extract(tx())
        assert f.is_new_location is True

    def test_velocity_after_5_updates(self):
        for i in range(5):
            self.eng.update(tx(transaction_id=f"t{i}"))
        f = self.eng.extract(tx(transaction_id="new"))
        assert f.txn_count_1h == 5

    def test_known_device_not_flagged(self):
        self.eng.update(tx())
        f = self.eng.extract(tx(transaction_id="t2"))
        assert f.is_new_device is False

    def test_new_location_detected(self):
        self.eng.update(tx(location="US"))
        f = self.eng.extract(tx(transaction_id="t2", location="JP"))
        assert f.is_new_location is True

    def test_night_flag_at_3am(self):
        import datetime

        night_ts = datetime.datetime(2024, 1, 1, 3, 0, 0, tzinfo=datetime.timezone.utc).timestamp()
        f = self.eng.extract(tx(timestamp=night_ts))
        assert f.is_night is True

    def test_day_flag_at_noon(self):
        import datetime

        day_ts = datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc).timestamp()
        f = self.eng.extract(tx(timestamp=day_ts))
        assert f.is_night is False

    def test_weekend_flag_saturday(self):
        import datetime

        sat = datetime.datetime(2024, 1, 6, 12, 0, 0, tzinfo=datetime.timezone.utc).timestamp()
        f = self.eng.extract(tx(timestamp=sat))
        assert f.is_weekend is True

    def test_merchant_risk_crypto(self):
        f = self.eng.extract(tx(merchant_category="crypto"))
        assert f.merchant_risk_score >= 0.8

    def test_merchant_risk_grocery_low(self):
        f = self.eng.extract(tx(merchant_category="grocery"))
        assert f.merchant_risk_score < 0.3

    def test_amount_log_correct(self):
        f = self.eng.extract(tx(amount=100.0))
        assert abs(f.amount_log - math.log1p(100.0)) < 0.001

    def test_feature_vector_to_array_length(self):
        f = self.eng.extract(tx())
        assert len(f.to_array()) == 22

    def test_math_helpers(self):
        assert abs(_mean([1, 2, 3]) - 2.0) < 0.001
        assert _mean([]) == 0.0
        assert _std([1.0]) == 0.0
        assert abs(_std([2, 4, 4, 4, 5, 5, 7, 9]) - 2.0) < 0.1


# ── Rules ─────────────────────────────────────────────────────────────────


class TestHighAmountRule:
    rule = HighAmountRule(critical=10_000, high=5_000)

    def test_critical_amount(self):
        r = self.rule.evaluate(tx(amount=15000), fv(amount=15000))
        assert r.triggered and r.score == 1.0

    def test_high_amount(self):
        r = self.rule.evaluate(tx(amount=7000), fv(amount=7000))
        assert r.triggered and r.score == 0.7

    def test_normal_amount(self):
        r = self.rule.evaluate(tx(amount=200), fv(amount=200))
        assert not r.triggered and r.score == 0.0


class TestVelocityRule:
    rule = VelocityRule(max_1h=10, max_24h=30)

    def test_high_1h(self):
        r = self.rule.evaluate(tx(), fv(txn_count_1h=12))
        assert r.triggered and r.score >= 0.8

    def test_high_24h(self):
        r = self.rule.evaluate(tx(), fv(txn_count_1h=5, txn_count_24h=35))
        assert r.triggered

    def test_normal(self):
        r = self.rule.evaluate(tx(), fv(txn_count_1h=3, txn_count_24h=10))
        assert not r.triggered


class TestNewDeviceRule:
    rule = NewDeviceRule()

    def test_new_device_new_location(self):
        r = self.rule.evaluate(tx(), fv(is_new_device=True, is_new_location=True))
        assert r.triggered and r.score >= 0.7

    def test_new_device_only(self):
        r = self.rule.evaluate(tx(), fv(is_new_device=True, is_new_location=False))
        assert r.triggered and r.score < 0.5

    def test_known_device(self):
        assert not self.rule.evaluate(tx(), fv(is_new_device=False)).triggered


class TestRuleEngine:
    def test_evaluates_all_rules(self):
        engine = RuleEngine()
        score, results = engine.evaluate(tx(), fv())
        assert 0.0 <= score <= 1.0
        assert len(results) == len(engine.rules)

    def test_score_capped_at_1(self):
        engine = RuleEngine()
        score, _ = engine.evaluate(
            tx(amount=50_000),
            fv(
                amount=50_000,
                amount_zscore=10.0,
                txn_count_1h=20,
                is_new_device=True,
                is_new_location=True,
            ),
        )
        assert score <= 1.0

    def test_broken_rule_no_crash(self):
        class Broken:
            name = "B"
            description = "B"
            weight = 1.0

            def evaluate(self, t, f):
                raise RuntimeError("crash")

        engine = RuleEngine(rules=[Broken()])
        score, results = engine.evaluate(tx(), fv())
        assert score == 0.0
        assert results[0].triggered is False

    def test_rule_results_have_reasons(self):
        engine = RuleEngine()
        _, results = engine.evaluate(tx(amount=15000), fv(amount=15000))
        triggered = [r for r in results if r.triggered]
        assert all(r.reason != "" for r in triggered)


# ── Graph Engine ──────────────────────────────────────────────────────────


class TestGraphEngine:
    def test_new_user_zero_ring_score(self):
        g = FraudGraphEngine()
        score = g.user_ring_score("NEW_USER", "DEV_A", "1.2.3.4")
        assert score == 0.0

    def test_shared_device_increases_score(self):
        g = FraudGraphEngine()
        for i in range(5):
            g.add_transaction(tx(user_id=f"U{i}", device_id="SHARED_DEV"))
        score = g.user_ring_score("U0", "SHARED_DEV", "1.2.3.4")
        assert score > 0.0

    def test_ring_detection_shared_device(self):
        g = FraudGraphEngine()
        for i in range(4):
            g.add_transaction(tx(user_id=f"U{i}", device_id="RING_DEV"))
        rings = g.detect_rings()
        assert len(rings) > 0
        assert any(r["entity"] == "RING_DEV" for r in rings)

    def test_graph_stats(self):
        g = FraudGraphEngine()
        g.add_transaction(tx())
        stats = g.get_stats()
        assert stats["total_nodes"] > 0

    def test_subgraph_for_user(self):
        g = FraudGraphEngine()
        g.add_transaction(tx(user_id="U_TEST"))
        sub = g.get_subgraph_for_user("U_TEST")
        assert "nodes" in sub and "edges" in sub
        assert len(sub["nodes"]) > 0


# ── Detector ─────────────────────────────────────────────────────────────


class TestFraudDetector:
    def setup_method(self):
        self.det = FraudDetector()

    def test_returns_valid_result(self):
        r = self.det.analyze(tx())
        assert 0.0 <= r.score <= 1.0
        assert r.transaction_id == "tx-001"
        assert r.latency_ms > 0

    def test_high_risk_flagged(self):
        r = self.det.analyze(tx(amount=15000, merchant_category="crypto"))
        assert r.decision.value in ("REVIEW", "BLOCK")

    def test_latency_under_500ms(self):
        r = self.det.analyze(tx())
        assert r.latency_ms < 500

    def test_fail_open_on_error(self):
        orig = self.det.features.extract
        self.det.features.extract = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("test"))
        r = self.det.analyze(tx())
        assert r.decision == Decision.ALLOW
        self.det.features.extract = orig

    def test_counter_increments(self):
        [self.det.analyze(tx(transaction_id=f"t{i}")) for i in range(5)]
        assert self.det._total_analyzed == 5

    def test_hydrate_warms_up(self):
        det2 = FraudDetector()
        txns = [tx(transaction_id=f"h{i}", user_id="U001") for i in range(10)]
        det2.hydrate(txns)
        assert det2._total_analyzed == 10

    def test_result_has_explanation(self):
        r = self.det.analyze(tx(amount=15000))
        assert r.explanation_text != ""

    def test_system_status(self):
        status = self.det.get_system_status()
        assert "total_analyzed" in status
        assert "xgb_trained" in status


# ── Generator ─────────────────────────────────────────────────────────────


class TestGenerator:
    def test_batch_count(self):
        gen = TransactionGenerator(n_users=10)
        assert len(gen.generate_batch(50)) == 50

    def test_unique_ids(self):
        gen = TransactionGenerator()
        txns = gen.generate_batch(100)
        assert len({t.transaction_id for t in txns}) == 100

    def test_positive_amounts(self):
        gen = TransactionGenerator()
        assert all(t.amount > 0 for t in gen.generate_batch(20))

    def test_stream_yields(self):
        gen = TransactionGenerator()
        t = next(gen.generate_stream(delay=0))
        assert isinstance(t, Transaction)

    def test_fraud_scenarios_generated(self):
        # FIX: 200 samples had a ~5% chance of zero high-value fraud
        # scenarios by pure chance (flaky test). 2000 samples reduces
        # that probability to statistically negligible, and the fixed
        # seed in conftest.py makes the result fully reproducible.
        gen = TransactionGenerator(n_users=20)
        txns = gen.generate_batch(2000)
        high_amt = [t for t in txns if t.amount > 5000]
        assert len(high_amt) > 0

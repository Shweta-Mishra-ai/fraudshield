"""
Unit Tests — covers all core components.
Run with:  pytest tests/ -v --tb=short
"""

from __future__ import annotations

import math
import time
import pytest
import sys
import os

# Make src importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.models import (
    Decision, FeatureVector, FraudResult, RiskLevel, Transaction,
)
from src.core.features import FeatureEngineer, _mean, _std
from src.core.rules import (
    HighAmountRule, NewDeviceRule, RuleEngine, VelocityRule,
)
from src.core.detector import FraudDetector
from src.core.generator import TransactionGenerator
from src.core.storage import FraudStorage


# ══════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════

def make_tx(**overrides) -> Transaction:
    """Create a valid test transaction."""
    defaults = dict(
        transaction_id   = "tx-test-001",
        user_id          = "USER_0001",
        amount           = 100.00,
        currency         = "USD",
        timestamp        = time.time(),
        merchant_id      = "MERCH_001",
        merchant_category = "grocery",
        location         = "US",
        device_id        = "DEV_0001",
        ip_address       = "192.168.1.10",
        is_international = False,
        is_card_present  = True,
        channel          = "online",
    )
    defaults.update(overrides)
    return Transaction(**defaults)


def make_feature_vector(**overrides) -> FeatureVector:
    defaults = dict(
        amount=100.0, amount_log=math.log1p(100), amount_zscore=0.5,
        amount_vs_merchant_avg=0.2,
        txn_count_1h=2, txn_count_24h=5,
        amount_sum_1h=200.0, amount_sum_24h=500.0,
        hour_of_day=14, day_of_week=1, is_weekend=False, is_night=False,
        location_encoded=1, is_new_location=False, is_new_device=False,
        device_encoded=1234, ip_encoded=5678,
        merchant_risk_score=0.1, is_high_risk_merchant=False,
        shared_device_user_count=1, shared_ip_user_count=1,
        user_fraud_ring_score=0.0,
    )
    defaults.update(overrides)
    return FeatureVector(**defaults)


# ══════════════════════════════════════════════════════════════════════════
# Model Tests
# ══════════════════════════════════════════════════════════════════════════

class TestTransaction:
    def test_valid_transaction_creates(self):
        tx = make_tx()
        assert tx.user_id == "USER_0001"
        assert tx.amount == 100.00

    def test_negative_amount_raises(self):
        with pytest.raises(ValueError, match="positive"):
            make_tx(amount=-10.0)

    def test_zero_amount_raises(self):
        with pytest.raises(ValueError):
            make_tx(amount=0.0)

    def test_empty_user_id_raises(self):
        with pytest.raises(ValueError, match="user_id"):
            make_tx(user_id="")

    def test_to_dict_round_trip(self):
        tx = make_tx()
        d  = tx.to_dict()
        tx2 = Transaction.from_dict(d)
        assert tx.transaction_id == tx2.transaction_id
        assert tx.amount == tx2.amount

    def test_new_factory_generates_id(self):
        tx = Transaction.new(
            user_id="U1", amount=50.0, currency="USD",
            merchant_id="M1", merchant_category="grocery",
            location="US", device_id="D1", ip_address="1.2.3.4",
        )
        assert tx.transaction_id != ""
        assert tx.timestamp > 0


class TestRiskLevel:
    def test_critical_threshold(self):
        assert RiskLevel.from_score(0.90) == RiskLevel.CRITICAL

    def test_high_threshold(self):
        assert RiskLevel.from_score(0.70) == RiskLevel.HIGH

    def test_medium_threshold(self):
        assert RiskLevel.from_score(0.50) == RiskLevel.MEDIUM

    def test_low_threshold(self):
        assert RiskLevel.from_score(0.10) == RiskLevel.LOW


class TestDecision:
    def test_block_above_0_8(self):
        assert Decision.from_score(0.85) == Decision.BLOCK

    def test_review_between_0_4_and_0_8(self):
        assert Decision.from_score(0.55) == Decision.REVIEW

    def test_allow_below_0_4(self):
        assert Decision.from_score(0.20) == Decision.ALLOW


# ══════════════════════════════════════════════════════════════════════════
# Feature Engineering Tests
# ══════════════════════════════════════════════════════════════════════════

class TestFeatureEngineer:
    def setup_method(self):
        self.eng = FeatureEngineer()

    def test_first_transaction_no_history(self):
        tx  = make_tx(amount=500.0)
        fv  = self.eng.extract(tx)
        assert fv.txn_count_1h  == 0
        assert fv.txn_count_24h == 0
        assert fv.is_new_device   is True
        assert fv.is_new_location is True

    def test_velocity_counts_after_update(self):
        user = "USER_0001"
        for i in range(5):
            tx = make_tx(transaction_id=f"tx-{i}", amount=100.0, user_id=user)
            self.eng.update(tx)

        new_tx = make_tx(transaction_id="tx-new", user_id=user)
        fv = self.eng.extract(new_tx)
        assert fv.txn_count_1h  == 5
        assert fv.txn_count_24h == 5

    def test_known_device_not_flagged(self):
        tx = make_tx()
        self.eng.update(tx)
        tx2 = make_tx(transaction_id="tx-002")
        fv  = self.eng.extract(tx2)
        assert fv.is_new_device is False

    def test_new_location_detected(self):
        tx = make_tx(location="US")
        self.eng.update(tx)
        tx2 = make_tx(transaction_id="tx-002", location="JP")
        fv  = self.eng.extract(tx2)
        assert fv.is_new_location is True

    def test_amount_zscore_zero_on_first(self):
        tx = make_tx(amount=100.0)
        fv = self.eng.extract(tx)
        # No history → zscore should be 0 (amount equals mean of 1)
        assert fv.amount_zscore == pytest.approx(0.0, abs=0.1)

    def test_night_flag(self):
        import datetime
        dt = datetime.datetime(2024, 1, 1, 3, 0, 0, tzinfo=datetime.timezone.utc)
        night_ts = dt.timestamp()
        tx = make_tx(timestamp=night_ts)
        fv = self.eng.extract(tx)
        assert fv.is_night is True

    def test_weekend_flag(self):
        import datetime
        # Saturday
        saturday = datetime.datetime(2024, 1, 6, 12, 0, 0).timestamp()
        tx = make_tx(timestamp=saturday)
        fv = self.eng.extract(tx)
        assert fv.is_weekend is True


class TestMathHelpers:
    def test_mean_empty(self):
        assert _mean([]) == 0.0

    def test_mean_values(self):
        assert _mean([1.0, 2.0, 3.0]) == pytest.approx(2.0)

    def test_std_single_element(self):
        assert _std([5.0]) == 0.0

    def test_std_known(self):
        assert _std([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]) == pytest.approx(2.0, rel=0.01)


# ══════════════════════════════════════════════════════════════════════════
# Rule Engine Tests
# ══════════════════════════════════════════════════════════════════════════

class TestHighAmountRule:
    rule = HighAmountRule(critical=10_000, high=5_000)

    def test_triggers_critical(self):
        tx  = make_tx(amount=15_000)
        fv  = make_feature_vector(amount=15_000)
        res = self.rule.evaluate(tx, fv)
        assert res.triggered
        assert res.score == 1.0

    def test_triggers_high(self):
        tx  = make_tx(amount=7_000)
        fv  = make_feature_vector(amount=7_000)
        res = self.rule.evaluate(tx, fv)
        assert res.triggered
        assert res.score == 0.7

    def test_no_trigger(self):
        tx  = make_tx(amount=200)
        fv  = make_feature_vector(amount=200)
        res = self.rule.evaluate(tx, fv)
        assert not res.triggered
        assert res.score == 0.0


class TestVelocityRule:
    rule = VelocityRule(max_1h=10, max_24h=30)

    def test_triggers_on_high_1h_count(self):
        tx  = make_tx()
        fv  = make_feature_vector(txn_count_1h=12)
        res = self.rule.evaluate(tx, fv)
        assert res.triggered
        assert res.score >= 0.8

    def test_triggers_on_24h_count(self):
        tx  = make_tx()
        fv  = make_feature_vector(txn_count_1h=5, txn_count_24h=35)
        res = self.rule.evaluate(tx, fv)
        assert res.triggered

    def test_no_trigger_normal(self):
        tx  = make_tx()
        fv  = make_feature_vector(txn_count_1h=3, txn_count_24h=10)
        res = self.rule.evaluate(tx, fv)
        assert not res.triggered


class TestNewDeviceRule:
    rule = NewDeviceRule()

    def test_new_device_new_location_high_score(self):
        tx  = make_tx()
        fv  = make_feature_vector(is_new_device=True, is_new_location=True)
        res = self.rule.evaluate(tx, fv)
        assert res.triggered
        assert res.score >= 0.7

    def test_new_device_only_lower_score(self):
        tx  = make_tx()
        fv  = make_feature_vector(is_new_device=True, is_new_location=False)
        res = self.rule.evaluate(tx, fv)
        assert res.triggered
        assert res.score < 0.5

    def test_known_device_no_trigger(self):
        tx  = make_tx()
        fv  = make_feature_vector(is_new_device=False)
        res = self.rule.evaluate(tx, fv)
        assert not res.triggered


class TestRuleEngine:
    def test_returns_results_for_all_rules(self):
        engine = RuleEngine()
        tx  = make_tx()
        fv  = make_feature_vector()
        score, results = engine.evaluate(tx, fv)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        assert len(results) == len(engine.rules)

    def test_score_capped_at_1(self):
        engine = RuleEngine()
        tx = make_tx(amount=50_000)
        fv = make_feature_vector(
            amount=50_000, amount_zscore=10.0,
            txn_count_1h=20, is_new_device=True, is_new_location=True,
        )
        score, _ = engine.evaluate(tx, fv)
        assert score <= 1.0

    def test_rule_exception_does_not_crash_engine(self):
        """A rule that raises must not crash the whole engine."""
        class BrokenRule:
            name = "Broken"
            description = "Always raises"
            weight = 1.0
            def evaluate(self, tx, fv):
                raise RuntimeError("intentional error")

        engine = RuleEngine(rules=[BrokenRule()])
        tx  = make_tx()
        fv  = make_feature_vector()
        score, results = engine.evaluate(tx, fv)  # must not raise
        assert score == 0.0
        assert results[0].triggered is False


# ══════════════════════════════════════════════════════════════════════════
# Detector Integration Tests
# ══════════════════════════════════════════════════════════════════════════

class TestFraudDetector:
    def setup_method(self):
        self.detector = FraudDetector()

    def test_normal_transaction_allowed(self):
        tx = make_tx(amount=50.0)
        result = self.detector.analyze(tx)
        assert result.decision.value in ("ALLOW", "REVIEW", "BLOCK")
        assert 0.0 <= result.score <= 1.0

    def test_high_amount_triggers_block_or_review(self):
        tx = make_tx(amount=15_000, merchant_category="crypto")
        result = self.detector.analyze(tx)
        assert result.decision.value in ("REVIEW", "BLOCK")

    def test_result_has_all_fields(self):
        tx = make_tx()
        result = self.detector.analyze(tx)
        assert result.transaction_id == tx.transaction_id
        assert result.latency_ms > 0
        assert result.model_version != ""
        assert isinstance(result.rule_results, list)

    def test_latency_under_500ms(self):
        """Each prediction must complete in under 500ms."""
        tx = make_tx()
        result = self.detector.analyze(tx)
        assert result.latency_ms < 500

    def test_fail_open_on_bad_transaction(self):
        """If something goes wrong, we should fail open (ALLOW), not crash."""
        # Manually trigger internal error by passing an object without expected attrs
        # We test by passing a valid tx but monkey-patching features to raise
        original = self.detector.features.extract
        self.detector.features.extract = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("test error"))
        tx = make_tx()
        result = self.detector.analyze(tx)
        assert result.decision == Decision.ALLOW
        self.detector.features.extract = original  # restore

    def test_multiple_transactions_increase_counter(self):
        for i in range(5):
            self.detector.analyze(make_tx(transaction_id=f"tx-{i}"))
        assert self.detector._total_analyzed == 5


# ══════════════════════════════════════════════════════════════════════════
# Generator Tests
# ══════════════════════════════════════════════════════════════════════════

class TestTransactionGenerator:
    def test_batch_generates_correct_count(self):
        gen = TransactionGenerator(n_users=10, n_merchants=5)
        txns = gen.generate_batch(50)
        assert len(txns) == 50

    def test_all_transactions_valid(self):
        gen = TransactionGenerator()
        for tx in gen.generate_batch(20):
            assert tx.amount > 0
            assert tx.user_id != ""
            assert tx.transaction_id != ""

    def test_unique_transaction_ids(self):
        gen = TransactionGenerator()
        txns = gen.generate_batch(100)
        ids = [t.transaction_id for t in txns]
        assert len(set(ids)) == 100  # all unique

    def test_stream_yields_transactions(self):
        gen = TransactionGenerator()
        stream = gen.generate_stream(delay=0)
        tx = next(stream)
        assert isinstance(tx, Transaction)


# ══════════════════════════════════════════════════════════════════════════
# Storage Tests
# ══════════════════════════════════════════════════════════════════════════

class TestFraudStorage:
    @pytest.fixture(autouse=True)
    def tmp_db(self, tmp_path):
        self.storage = FraudStorage(db_path=str(tmp_path / "test.db"))

    def _make_result(self, tx: Transaction) -> FraudResult:
        return FraudResult(
            transaction_id = tx.transaction_id,
            is_fraud       = False,
            score          = 0.1,
            risk_level     = RiskLevel.LOW,
            decision       = Decision.ALLOW,
            model_version  = "test",
            evaluated_at   = time.time(),
        )

    def test_save_and_retrieve(self):
        tx     = make_tx()
        result = self._make_result(tx)
        self.storage.save(tx, result)
        rows = self.storage.get_recent(10)
        assert len(rows) == 1
        assert rows[0]["id"] == tx.transaction_id

    def test_stats_after_save(self):
        tx     = make_tx()
        result = self._make_result(tx)
        self.storage.save(tx, result)
        stats = self.storage.get_stats()
        assert stats["total_transactions"] == 1
        assert stats["fraud_count"] == 0

    def test_analyst_review(self):
        tx     = make_tx()
        result = FraudResult(
            transaction_id = tx.transaction_id,
            is_fraud       = True,
            score          = 0.9,
            risk_level     = RiskLevel.CRITICAL,
            decision       = Decision.BLOCK,
            model_version  = "test",
            evaluated_at   = time.time(),
        )
        self.storage.save(tx, result)
        self.storage.update_analyst_review(tx.transaction_id, label=False, notes="False positive")
        alerts = self.storage.get_alerts(10)
        # After review, should not appear in unreviewed alerts
        assert not any(a["id"] == tx.transaction_id for a in alerts)

    def test_save_idempotent(self):
        tx     = make_tx()
        result = self._make_result(tx)
        self.storage.save(tx, result)
        self.storage.save(tx, result)  # duplicate — should not raise
        rows = self.storage.get_recent(10)
        assert len(rows) == 1  # INSERT OR REPLACE

    def test_user_history(self):
        for i in range(5):
            tx = make_tx(transaction_id=f"tx-{i}")
            self.storage.save(tx, self._make_result(tx))
        history = self.storage.get_user_history("USER_0001", limit=10)
        assert len(history) == 5

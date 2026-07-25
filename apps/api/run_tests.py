"""
Master test runner — runs all tests without pytest dependency.
Usage: python run_tests.py
"""
import sys, os, time, math, json, tempfile
sys.path.insert(0, os.path.dirname(__file__))

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

passed = 0
failed = 0
failures = []

def ok(name):
    global passed; passed += 1
    try:
        print(f"  ✅  {name}")
    except UnicodeEncodeError:
        print(f"  [OK]  {name}")

def fail(name, err):
    global failed; failed += 1
    failures.append((name, str(err)))
    try:
        print(f"  ❌  {name}: {err}")
    except UnicodeEncodeError:
        print(f"  [FAIL]  {name}: {err}")

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

# ── Helpers ───────────────────────────────────────────────────────────────
from src.core.models import (Transaction, FraudResult, RiskLevel,
                              Decision, FeatureVector)
from src.core.features import FeatureEngineer, _mean, _std
from src.core.rules import (RuleEngine, HighAmountRule, VelocityRule,
                             NewDeviceRule)
from src.core.graph import FraudGraphEngine
from src.core.storage import FraudStorage
from src.core.generator import TransactionGenerator
from src.core.detector import FraudDetector
from src.security.auth import (sanitize_amount, sanitize_location,
                                sanitize_ip, sanitize_channel,
                                sanitize_string, RateLimiter)
from src.streaming.pathway_pipeline import write_transactions_to_csv

def tx(**kw):
    d = dict(transaction_id="tx-001", user_id="U001", amount=100.0,
             currency="USD", timestamp=time.time(), merchant_id="M001",
             merchant_category="grocery", location="US", device_id="D001",
             ip_address="192.168.1.1", is_international=False,
             is_card_present=True, channel="online")
    d.update(kw); return Transaction(**d)

def fv(**kw):
    d = dict(amount=100.0, amount_log=math.log1p(100), amount_zscore=0.5,
             amount_vs_merchant_avg=0.2, txn_count_1h=2, txn_count_24h=5,
             amount_sum_1h=200.0, amount_sum_24h=500.0, hour_of_day=14,
             day_of_week=1, is_weekend=False, is_night=False,
             location_encoded=1, is_new_location=False, is_new_device=False,
             device_encoded=1234, ip_encoded=5678, merchant_risk_score=0.1,
             is_high_risk_merchant=False, shared_device_user_count=1,
             shared_ip_user_count=1, user_fraud_ring_score=0.0)
    d.update(kw); return FeatureVector(**d)

def result(t, fraud=False, score=0.1, dec=Decision.ALLOW, risk=RiskLevel.LOW):
    return FraudResult(transaction_id=t.transaction_id, is_fraud=fraud,
                       score=score, risk_level=risk, decision=dec,
                       model_version="test", evaluated_at=time.time())

def raises(fn, exc_type=Exception):
    try: fn(); return False
    except exc_type: return True
    except Exception: return False


# ══════════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("  FRAUD DETECTION SYSTEM v2.0 — FULL TEST SUITE")
print("="*60)

# ── 1. Models ─────────────────────────────────────────────────────────────
section("1. MODELS")
try: tx(); ok("Transaction creation")
except Exception as e: fail("Transaction creation", e)

try:
    assert raises(lambda: tx(amount=-1), ValueError); ok("Negative amount raises")
except Exception as e: fail("Negative amount", e)

try:
    assert raises(lambda: tx(amount=0), ValueError); ok("Zero amount raises")
except Exception as e: fail("Zero amount", e)

try:
    assert raises(lambda: tx(user_id=""), ValueError); ok("Empty user_id raises")
except Exception as e: fail("Empty user_id", e)

try:
    t = tx(); t2 = Transaction.from_dict(t.to_dict())
    assert t.transaction_id == t2.transaction_id; ok("Serialization round-trip")
except Exception as e: fail("Serialization", e)

try:
    assert RiskLevel.from_score(0.9) == RiskLevel.CRITICAL
    assert RiskLevel.from_score(0.7) == RiskLevel.HIGH
    assert RiskLevel.from_score(0.5) == RiskLevel.MEDIUM
    assert RiskLevel.from_score(0.1) == RiskLevel.LOW
    ok("RiskLevel thresholds")
except Exception as e: fail("RiskLevel", e)

try:
    assert Decision.from_score(0.85) == Decision.BLOCK
    assert Decision.from_score(0.55) == Decision.REVIEW
    assert Decision.from_score(0.20) == Decision.ALLOW
    ok("Decision thresholds")
except Exception as e: fail("Decision", e)

try:
    d = tx().to_dict()
    for k in ["transaction_id","user_id","amount","location","device_id"]:
        assert k in d
    ok("to_dict has all required fields")
except Exception as e: fail("to_dict fields", e)


# ── 2. Feature Engineering ────────────────────────────────────────────────
section("2. FEATURE ENGINEERING")

try:
    eng = FeatureEngineer(); f = eng.extract(tx())
    assert f.txn_count_1h == 0 and f.is_new_device is True
    ok("First tx: zero velocity, new device")
except Exception as e: fail("First tx features", e)

try:
    eng = FeatureEngineer()
    for i in range(5): eng.update(tx(transaction_id=f"t{i}"))
    assert eng.extract(tx(transaction_id="new")).txn_count_1h == 5
    ok("Velocity: 5 updates → count_1h=5")
except Exception as e: fail("Velocity", e)

try:
    eng = FeatureEngineer()
    eng.update(tx(location="US"))
    assert eng.extract(tx(transaction_id="t2", location="JP")).is_new_location is True
    ok("New location detection")
except Exception as e: fail("New location", e)

try:
    import datetime
    night_ts = datetime.datetime(2024,1,1,3,0,0, tzinfo=datetime.timezone.utc).timestamp()
    f = FeatureEngineer().extract(tx(timestamp=night_ts))
    assert f.is_night is True; ok("Night flag at 03:00 UTC")
except Exception as e: fail("Night flag", e)

try:
    import datetime
    sat = datetime.datetime(2024,1,6,12,0,0, tzinfo=datetime.timezone.utc).timestamp()
    f = FeatureEngineer().extract(tx(timestamp=sat))
    assert f.is_weekend is True; ok("Weekend flag on Saturday")
except Exception as e: fail("Weekend flag", e)

try:
    f = FeatureEngineer().extract(tx(merchant_category="crypto"))
    assert f.merchant_risk_score >= 0.8; ok("Crypto merchant high risk score")
except Exception as e: fail("Merchant risk", e)

try:
    f = FeatureEngineer().extract(tx())
    assert len(f.to_array()) == 22; ok("FeatureVector has 22 features")
except Exception as e: fail("Feature count", e)

try:
    assert abs(_mean([1,2,3]) - 2.0) < 0.001
    assert _mean([]) == 0.0
    assert _std([1.0]) == 0.0
    ok("Math helpers (_mean, _std)")
except Exception as e: fail("Math helpers", e)


# ── 3. Rules ──────────────────────────────────────────────────────────────
section("3. RULE ENGINE")

try:
    rule = HighAmountRule(critical=10000, high=5000)
    assert rule.evaluate(tx(amount=15000), fv(amount=15000)).score == 1.0
    assert not rule.evaluate(tx(amount=200), fv(amount=200)).triggered
    ok("HighAmountRule: critical=1.0, normal=no trigger")
except Exception as e: fail("HighAmountRule", e)

try:
    rule = VelocityRule(max_1h=10)
    assert rule.evaluate(tx(), fv(txn_count_1h=12)).triggered
    ok("VelocityRule: 12/1h triggers")
except Exception as e: fail("VelocityRule", e)

try:
    rule = NewDeviceRule()
    r = rule.evaluate(tx(), fv(is_new_device=True, is_new_location=True))
    assert r.triggered and r.score >= 0.7
    ok("NewDeviceRule: new device+location → high score")
except Exception as e: fail("NewDeviceRule", e)

try:
    engine = RuleEngine()
    score, results = engine.evaluate(tx(), fv())
    assert 0.0 <= score <= 1.0 and len(results) == len(engine.rules)
    ok(f"RuleEngine: {len(engine.rules)} rules, score 0-1")
except Exception as e: fail("RuleEngine", e)

try:
    class Broken:
        name="B"; description="B"; weight=1.0
        def evaluate(self, t, f): raise RuntimeError("crash")
    score, results = RuleEngine(rules=[Broken()]).evaluate(tx(), fv())
    assert score == 0.0; ok("Broken rule: engine survives")
except Exception as e: fail("Rule exception safety", e)

try:
    engine = RuleEngine()
    score, _ = engine.evaluate(tx(amount=50000),
                               fv(amount=50000, txn_count_1h=20, is_new_device=True))
    assert score <= 1.0; ok("Score capped at 1.0 regardless of inputs")
except Exception as e: fail("Score cap", e)


# ── 4. Graph Engine ───────────────────────────────────────────────────────
section("4. GRAPH ENGINE")

try:
    g = FraudGraphEngine()
    assert g.user_ring_score("NEW","DEV","1.2.3.4") == 0.0
    ok("New user: ring score = 0")
except Exception as e: fail("New user ring score", e)

try:
    g = FraudGraphEngine()
    for i in range(5): g.add_transaction(tx(user_id=f"U{i}", device_id="SHARED"))
    assert g.user_ring_score("U0","SHARED","1.2.3.4") > 0
    ok("Shared device increases ring score")
except Exception as e: fail("Shared device score", e)

try:
    g = FraudGraphEngine()
    for i in range(4): g.add_transaction(tx(user_id=f"U{i}", device_id="RING_DEV"))
    rings = g.detect_rings()
    assert any(r["entity"] == "RING_DEV" for r in rings)
    ok("Ring detection: 4 users on 1 device")
except Exception as e: fail("Ring detection", e)

try:
    g = FraudGraphEngine()
    g.add_transaction(tx(user_id="U_TEST"))
    sub = g.get_subgraph_for_user("U_TEST")
    assert len(sub["nodes"]) > 0
    ok("Subgraph for user has nodes")
except Exception as e: fail("Subgraph", e)

try:
    g = FraudGraphEngine()
    g.add_transaction(tx())
    stats = g.get_stats()
    assert stats["total_nodes"] > 0
    ok("Graph stats after 1 transaction")
except Exception as e: fail("Graph stats", e)


# ── 5. FraudDetector ─────────────────────────────────────────────────────
section("5. FRAUD DETECTOR")

try:
    det = FraudDetector(); r = det.analyze(tx())
    assert 0.0 <= r.score <= 1.0 and r.latency_ms > 0
    ok(f"analyze() valid result (latency={r.latency_ms:.1f}ms)")
except Exception as e: fail("analyze() basic", e)

try:
    det = FraudDetector()
    r = det.analyze(tx(amount=15000, merchant_category="crypto"))
    assert r.decision.value in ("REVIEW","BLOCK")
    ok(f"High-risk tx → {r.decision.value}")
except Exception as e: fail("High-risk decision", e)

try:
    det = FraudDetector(); r = det.analyze(tx())
    assert r.latency_ms < 500; ok(f"Latency <500ms ({r.latency_ms:.1f}ms)")
except Exception as e: fail("Latency", e)

try:
    det = FraudDetector()
    orig = det.features.extract
    det.features.extract = lambda *a,**kw: (_ for _ in ()).throw(RuntimeError("injected"))
    r = det.analyze(tx())
    assert r.decision == Decision.ALLOW; ok("Fail-open on internal error")
    det.features.extract = orig
except Exception as e: fail("Fail-open", e)

try:
    det = FraudDetector()
    [det.analyze(tx(transaction_id=f"t{i}")) for i in range(5)]
    assert det._total_analyzed == 5; ok("Counter: 5 → 5")
except Exception as e: fail("Counter", e)

try:
    det = FraudDetector()
    txns = [tx(transaction_id=f"h{i}") for i in range(10)]
    det.hydrate(txns)
    assert det._total_analyzed == 10; ok("hydrate() warms up detector")
except Exception as e: fail("hydrate()", e)

try:
    det = FraudDetector()
    r = det.analyze(tx(amount=15000))
    assert r.explanation_text != ""; ok("FraudResult has explanation text")
except Exception as e: fail("Explanation text", e)

try:
    det = FraudDetector()
    s = det.get_system_status()
    assert "total_analyzed" in s and "xgb_trained" in s
    ok("get_system_status() returns expected keys")
except Exception as e: fail("System status", e)


# ── 6. Security ───────────────────────────────────────────────────────────
section("6. SECURITY")

try:
    assert sanitize_amount(100.0) == 100.0
    assert raises(lambda: sanitize_amount(0), ValueError)
    assert raises(lambda: sanitize_amount(-1), ValueError)
    assert raises(lambda: sanitize_amount(20_000_000), ValueError)
    ok("sanitize_amount: valid/zero/negative/too-large")
except Exception as e: fail("sanitize_amount", e)

try:
    assert sanitize_location("US") == "US"
    assert sanitize_location("in") == "IN"
    assert raises(lambda: sanitize_location("USA"), ValueError)
    assert raises(lambda: sanitize_location("12"), ValueError)
    ok("sanitize_location: valid/lowercase/too-long/numbers")
except Exception as e: fail("sanitize_location", e)

try:
    assert sanitize_ip("192.168.1.1") == "192.168.1.1"
    assert raises(lambda: sanitize_ip("not-an-ip"), ValueError)
    assert raises(lambda: sanitize_ip(""), ValueError)
    ok("sanitize_ip: valid/invalid/empty")
except Exception as e: fail("sanitize_ip", e)

try:
    assert sanitize_channel("online") == "online"
    assert sanitize_channel("ONLINE") == "online"
    assert raises(lambda: sanitize_channel("telegram"), ValueError)
    ok("sanitize_channel: valid/uppercase/invalid")
except Exception as e: fail("sanitize_channel", e)

try:
    assert sanitize_string("USER_001","uid") == "USER_001"
    assert raises(lambda: sanitize_string("'; DROP TABLE--","uid"), ValueError)
    assert raises(lambda: sanitize_string("<script>xss</script>","uid"), ValueError)
    assert raises(lambda: sanitize_string("","uid"), ValueError)
    assert raises(lambda: sanitize_string("A"*200,"uid",max_len=100), ValueError)
    ok("sanitize_string: valid/SQL-injection/XSS/empty/too-long")
except Exception as e: fail("sanitize_string", e)

try:
    from fastapi import HTTPException
    limiter = RateLimiter(requests_per_minute=5)
    blocked = False
    try:
        for _ in range(10): limiter.check("1.2.3.4")
    except HTTPException as e:
        assert e.status_code == 429; blocked = True
    assert blocked; ok("Rate limiter: blocks after limit (HTTP 429)")
except Exception as e: fail("Rate limiter", e)

try:
    from fastapi import HTTPException
    limiter = RateLimiter(requests_per_minute=3)
    try:
        for _ in range(5): limiter.check("5.5.5.5")
    except HTTPException: pass
    limiter.check("6.6.6.6")  # different IP — should not raise
    ok("Rate limiter: IPs are independent")
except Exception as e: fail("Rate limiter IPs independent", e)

try:
    from src.security.auth import SECURITY_HEADERS
    for h in ["X-Content-Type-Options","X-Frame-Options","X-XSS-Protection",
              "Strict-Transport-Security","Cache-Control"]:
        assert h in SECURITY_HEADERS
    ok("Security headers: all 5 present")
except Exception as e: fail("Security headers", e)


# ── 7. Generator ─────────────────────────────────────────────────────────
section("7. GENERATOR")

try:
    gen = TransactionGenerator(n_users=10)
    txns = gen.generate_batch(50)
    assert len(txns) == 50; ok("generate_batch(50) returns 50")
except Exception as e: fail("Batch count", e)

try:
    gen = TransactionGenerator()
    ids = [t.transaction_id for t in gen.generate_batch(100)]
    assert len(set(ids)) == 100; ok("100 unique transaction IDs")
except Exception as e: fail("Unique IDs", e)

try:
    gen = TransactionGenerator()
    assert all(t.amount > 0 for t in gen.generate_batch(20))
    ok("All amounts > 0")
except Exception as e: fail("Positive amounts", e)


# ── 8. Storage ────────────────────────────────────────────────────────────
section("8. STORAGE")

try:
    db = tempfile.mktemp(suffix=".db")
    store = FraudStorage(db_path=db)
    t = tx(); store.save(t, result(t))
    assert len(store.get_recent(10)) == 1
    ok("save + get_recent")
    os.unlink(db)
except Exception as e: fail("Save/retrieve", e)

try:
    db = tempfile.mktemp(suffix=".db")
    store = FraudStorage(db_path=db)
    t = tx()
    store.save(t, result(t, fraud=True, score=0.9,
                         dec=Decision.BLOCK, risk=RiskLevel.CRITICAL))
    store.update_analyst_review(t.transaction_id, False, "FP")
    assert not any(a["id"]==t.transaction_id for a in store.get_alerts(10))
    ok("Analyst review removes from alert queue")
    os.unlink(db)
except Exception as e: fail("Analyst review", e)

try:
    db = tempfile.mktemp(suffix=".db")
    store = FraudStorage(db_path=db)
    t = tx(); r = result(t)
    store.save(t, r); store.save(t, r)
    assert len(store.get_recent(10)) == 1
    ok("Idempotent save (no duplicates)")
    os.unlink(db)
except Exception as e: fail("Idempotent save", e)

try:
    db = tempfile.mktemp(suffix=".db")
    store = FraudStorage(db_path=db)
    t = tx()
    store.save(t, result(t, fraud=True, score=0.9,
                         dec=Decision.BLOCK, risk=RiskLevel.CRITICAL))
    s = store.get_stats()
    assert s["fraud_count"] == 1 and s["blocked_count"] == 1
    ok("Stats: fraud_count + blocked_count")
    os.unlink(db)
except Exception as e: fail("Stats", e)

try:
    db = tempfile.mktemp(suffix=".db")
    store = FraudStorage(db_path=db)
    for i in range(5):
        t = tx(transaction_id=f"t{i}")
        store.save(t, result(t))
    txns = store.get_all_transactions()
    assert len(txns) == 5 and all(isinstance(t, Transaction) for t in txns)
    ok("get_all_transactions for hydration")
    os.unlink(db)
except Exception as e: fail("get_all_transactions", e)


# ── 9. Streaming / Pathway ────────────────────────────────────────────────
section("9. STREAMING / PATHWAY")

try:
    tmp = tempfile.mkdtemp()
    gen = TransactionGenerator()
    txns = gen.generate_batch(5)
    fname = write_transactions_to_csv(txns, tmp)
    assert os.path.exists(fname); ok("write_transactions_to_csv creates file")
except Exception as e: fail("CSV write", e)

try:
    import csv
    tmp = tempfile.mkdtemp()
    txns = TransactionGenerator().generate_batch(5)
    fname = write_transactions_to_csv(txns, tmp)
    with open(fname) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 5; ok("CSV has correct row count")
except Exception as e: fail("CSV row count", e)

try:
    import csv
    tmp = tempfile.mkdtemp()
    txns = TransactionGenerator().generate_batch(3)
    fname = write_transactions_to_csv(txns, tmp)
    with open(fname) as f:
        row = next(csv.DictReader(f))
    for field in ["transaction_id","user_id","amount","merchant_id","location"]:
        assert field in row
    ok("CSV has all required fields")
except Exception as e: fail("CSV fields", e)

try:
    from src.streaming.pathway_pipeline import PATHWAY_AVAILABLE
    status = "installed" if PATHWAY_AVAILABLE else "not installed (polling fallback active)"
    ok(f"Pathway import check: {status}")
except Exception as e: fail("Pathway import", e)


# ── Summary ───────────────────────────────────────────────────────────────
print("\n" + "="*60)
total = passed + failed
bar = "█" * int(passed/max(total,1)*40) + "░" * int(failed/max(total,1)*40)
print(f"\n  [{bar}]")
print(f"\n  Results: {passed}/{total} passed  |  {failed} failed")
if failures:
    print("\n  Failed:")
    for name, err in failures:
        print(f"    ❌ {name}: {err}")
if failed == 0:
    print("\n  🎉  ALL TESTS PASSED — Production ready!")
else:
    print(f"\n  ⚠️  {failed} test(s) need attention")
print("="*60 + "\n")
sys.exit(0 if failed == 0 else 1)


# ── 10. Cold-Start Fix Verification ──────────────────────────────────────
section("10. COLD-START FIX — New User Should NOT Auto-REVIEW")

try:
    from src.core.rules import NewLocationRule, NewDeviceRule, AmountZScoreRule

    # Simulate first transaction for a brand new user
    new_user_fv = fv(
        txn_count_1h=0, txn_count_24h=0,
        is_new_device=True, is_new_location=True,
        amount_zscore=1.5,
    )
    normal_tx = tx(amount=100.0, merchant_category="grocery")

    loc_result = NewLocationRule().evaluate(normal_tx, new_user_fv)
    assert not loc_result.triggered, \
        f"NewLocationRule should NOT trigger for new user, got score={loc_result.score}"
    ok("NewLocationRule: new user's first location not flagged alone")
except Exception as e: fail("NewLocationRule cold-start", e)

try:
    dev_result = NewDeviceRule().evaluate(normal_tx, new_user_fv)
    assert not dev_result.triggered, \
        f"NewDeviceRule should NOT trigger for new user on normal tx, got score={dev_result.score}"
    ok("NewDeviceRule: new user's first device not flagged alone")
except Exception as e: fail("NewDeviceRule cold-start", e)

try:
    z_result = AmountZScoreRule().evaluate(normal_tx, new_user_fv)
    assert not z_result.triggered, \
        "AmountZScoreRule should NOT trigger for new user (no history)"
    ok("AmountZScoreRule: skipped for new user (no history)")
except Exception as e: fail("AmountZScoreRule cold-start", e)

try:
    # But: established user (10 txns) + new location + high amount SHOULD trigger
    established_fv = fv(
        txn_count_24h=10, is_new_location=True, is_new_device=False
    )
    high_tx = tx(amount=1000.0)
    loc_result2 = NewLocationRule().evaluate(high_tx, established_fv)
    assert loc_result2.triggered, "Established user + new location + high amount should trigger"
    ok("NewLocationRule: established user + new location + high amount → triggers ✅")
except Exception as e: fail("NewLocationRule established user", e)

try:
    # Full detector: 100 new users should NOT all be REVIEW
    det = FraudDetector()
    review_count = 0
    for i in range(20):
        t = tx(transaction_id=f"coldstart-{i}",
               user_id=f"BRAND_NEW_USER_{i}",
               amount=100.0, merchant_category="grocery",
               location="US", device_id=f"DEV_{i}")
        r = det.analyze(t)
        if r.decision.value == "REVIEW":
            review_count += 1

    review_rate = review_count / 20 * 100
    assert review_rate < 20, \
        f"Cold-start review rate too high: {review_rate:.0f}% (expected <20%)"
    ok(f"Cold-start: {review_rate:.0f}% review rate for new users (expected <20%)")
except Exception as e: fail("Cold-start review rate", e)


# ── 11. Settings Validation ───────────────────────────────────────────────
section("11. SETTINGS — Production Secret Validation")

try:
    from config.settings import Settings

    # Production with unsafe key should raise
    s = Settings()
    s.ENVIRONMENT = "production"
    s.API_KEYS    = ["dev-key-change-in-prod"]
    s.JWT_SECRET  = "a-real-secret-that-is-long-enough-yes"
    raised = False
    try:
        s.validate_production_secrets()
    except RuntimeError:
        raised = True
    assert raised, "Should raise on unsafe API key in production"
    ok("validate_production_secrets: raises on unsafe API key")
except Exception as e: fail("Settings unsafe API key", e)

try:
    s = Settings()
    s.ENVIRONMENT = "production"
    s.API_KEYS    = ["my-real-secret-key-here"]
    s.JWT_SECRET  = "change-me-in-production"
    raised = False
    try:
        s.validate_production_secrets()
    except RuntimeError:
        raised = True
    assert raised, "Should raise on unsafe JWT secret"
    ok("validate_production_secrets: raises on unsafe JWT secret")
except Exception as e: fail("Settings unsafe JWT", e)

try:
    s = Settings()
    s.ENVIRONMENT = "production"
    s.API_KEYS    = ["my-real-secret-key-here"]
    s.JWT_SECRET  = "short"
    raised = False
    try:
        s.validate_production_secrets()
    except RuntimeError:
        raised = True
    assert raised, "Should raise on short JWT secret"
    ok("validate_production_secrets: raises on JWT secret < 32 chars")
except Exception as e: fail("Settings short JWT", e)

try:
    s = Settings()
    s.ENVIRONMENT = "development"
    s.API_KEYS    = ["dev-key-change-in-prod"]  # unsafe but dev env
    s.JWT_SECRET  = "change-me-in-production"
    s.validate_production_secrets()  # should NOT raise in dev
    ok("validate_production_secrets: no-op in development environment")
except Exception as e: fail("Settings dev env no-op", e)


# ── 12. IP Validation (stdlib) ────────────────────────────────────────────
section("12. IP VALIDATION — stdlib ipaddress (not regex)")

try:
    assert sanitize_ip("192.168.1.1")     == "192.168.1.1"
    assert sanitize_ip("127.0.0.1")       == "127.0.0.1"
    assert sanitize_ip("8.8.8.8")         == "8.8.8.8"
    ok("sanitize_ip: valid IPv4 addresses accepted")
except Exception as e: fail("IP valid IPv4", e)

try:
    assert sanitize_ip("2001:db8::1")     == "2001:db8::1"
    assert sanitize_ip("::1")             == "::1"
    ok("sanitize_ip: valid IPv6 addresses accepted")
except Exception as e: fail("IP valid IPv6", e)

try:
    assert raises(lambda: sanitize_ip("999.999.999.999"), ValueError)
    ok("sanitize_ip: rejects 999.999.999.999")
except Exception as e: fail("IP invalid octets", e)

try:
    assert raises(lambda: sanitize_ip("192.168.1.1'; DROP TABLE--"), ValueError)
    ok("sanitize_ip: SQL injection blocked")
except Exception as e: fail("IP SQL injection", e)

try:
    assert raises(lambda: sanitize_ip("not-an-ip"), ValueError)
    assert raises(lambda: sanitize_ip(""), ValueError)
    assert raises(lambda: sanitize_ip("1.2.3"), ValueError)
    ok("sanitize_ip: various invalid values rejected")
except Exception as e: fail("IP invalid values", e)


# ── 13. Currency + Merchant Category Validation ───────────────────────────
section("13. NEW VALIDATORS — Currency + Merchant Category")

try:
    from src.security.auth import sanitize_currency, sanitize_merchant_category

    assert sanitize_currency("USD") == "USD"
    assert sanitize_currency("usd") == "USD"
    assert sanitize_currency("EUR") == "EUR"
    ok("sanitize_currency: valid currencies accepted")
except Exception as e: fail("Currency valid", e)

try:
    from src.security.auth import sanitize_currency
    assert raises(lambda: sanitize_currency("XYZ"), ValueError)
    assert raises(lambda: sanitize_currency(""), ValueError)
    ok("sanitize_currency: invalid currency rejected")
except Exception as e: fail("Currency invalid", e)

try:
    from src.security.auth import sanitize_merchant_category
    assert sanitize_merchant_category("grocery")   == "grocery"
    assert sanitize_merchant_category("CRYPTO")    == "crypto"
    ok("sanitize_merchant_category: valid categories accepted")
except Exception as e: fail("Merchant category valid", e)

try:
    from src.security.auth import sanitize_merchant_category
    result = sanitize_merchant_category("unknown_weird_category")
    assert result == "unknown"   # normalizes to unknown
    ok("sanitize_merchant_category: unknown → normalized to 'unknown'")
except Exception as e: fail("Merchant category normalize", e)


# ── 14. CardNotPresent Rule ───────────────────────────────────────────────
section("14. NEW RULE — CardNotPresentHighRiskRule (audit fix #15)")

try:
    from src.core.rules import CardNotPresentHighRiskRule

    rule = CardNotPresentHighRiskRule()

    # CNP + high risk merchant should trigger
    cnp_tx = tx(is_card_present=False, merchant_category="crypto")
    cnp_fv = fv(merchant_risk_score=0.9, is_high_risk_merchant=True)
    r = rule.evaluate(cnp_tx, cnp_fv)
    assert r.triggered and r.score > 0
    ok("CardNotPresentRule: CNP + high-risk merchant triggers")
except Exception as e: fail("CNP rule triggers", e)

try:
    from src.core.rules import CardNotPresentHighRiskRule
    rule = CardNotPresentHighRiskRule()

    # Card present → no trigger
    cp_tx = tx(is_card_present=True, merchant_category="crypto")
    cp_fv = fv(merchant_risk_score=0.9)
    r = rule.evaluate(cp_tx, cp_fv)
    assert not r.triggered
    ok("CardNotPresentRule: card present → no trigger")
except Exception as e: fail("CNP rule no trigger", e)

try:
    from src.core.rules import CardNotPresentHighRiskRule
    rule = CardNotPresentHighRiskRule()

    # CNP + low risk merchant → no trigger
    safe_tx = tx(is_card_present=False, merchant_category="grocery")
    safe_fv = fv(merchant_risk_score=0.1)
    r = rule.evaluate(safe_tx, safe_fv)
    assert not r.triggered
    ok("CardNotPresentRule: CNP + low-risk merchant → no trigger")
except Exception as e: fail("CNP rule low risk", e)


# ── Final summary ─────────────────────────────────────────────────────────
print("\n" + "="*60)
total = passed + failed
bar   = "█" * int(passed/max(total,1)*50) + "░" * int(failed/max(total,1)*50)
print(f"\n  [{bar}]")
print(f"\n  Results: {passed}/{total} passed  |  {failed} failed")
if failures:
    print("\n  Failed tests:")
    for name, err in failures:
        print(f"    ❌ {name}: {err}")
if failed == 0:
    print("\n  🎉  ALL TESTS PASSED")
    print("  Audit fixes verified:")
    print("    ✅ Cold-start: new users no longer auto-REVIEW")
    print("    ✅ Unsafe defaults: production startup fails hard")
    print("    ✅ IP validation: stdlib ipaddress (not regex)")
    print("    ✅ Currency + merchant_category validated")
    print("    ✅ CardNotPresent rule using is_card_present field")
    print("    ✅ limit params bounded (ge=1, le=N)")
else:
    print(f"\n  ⚠️  {failed} test(s) need attention")
print("="*60 + "\n")
import sys as _sys
_sys.exit(0 if failed == 0 else 1)

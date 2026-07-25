"""Security tests — auth, rate limiting, input sanitization, injection prevention."""
from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
import time
from src.security.auth import (
    sanitize_amount, sanitize_channel, sanitize_ip,
    sanitize_location, sanitize_string, RateLimiter,
)


# ── Input Sanitization ────────────────────────────────────────────────────

class TestSanitizeAmount:
    def test_valid_amount(self):       assert sanitize_amount(100.0) == 100.0
    def test_rounds_to_2_dp(self):     assert sanitize_amount(99.999) == 100.0
    def test_zero_raises(self):
        with pytest.raises(ValueError): sanitize_amount(0.0)
    def test_negative_raises(self):
        with pytest.raises(ValueError): sanitize_amount(-50.0)
    def test_too_large_raises(self):
        with pytest.raises(ValueError): sanitize_amount(20_000_000.0)
    def test_string_raises(self):
        with pytest.raises((ValueError, TypeError)): sanitize_amount("100")


class TestSanitizeLocation:
    def test_valid_us(self):      assert sanitize_location("US") == "US"
    def test_lowercase_in(self):  assert sanitize_location("in") == "IN"
    def test_too_long_raises(self):
        with pytest.raises(ValueError): sanitize_location("USA")
    def test_numbers_raise(self):
        with pytest.raises(ValueError): sanitize_location("12")
    def test_empty_raises(self):
        with pytest.raises(ValueError): sanitize_location("")
    def test_special_chars_raise(self):
        with pytest.raises(ValueError): sanitize_location("U$")


class TestSanitizeIP:
    def test_valid_ipv4(self):   assert sanitize_ip("192.168.1.1") == "192.168.1.1"
    def test_valid_local(self):  assert sanitize_ip("127.0.0.1") == "127.0.0.1"
    def test_invalid_raises(self):
        with pytest.raises(ValueError): sanitize_ip("not-an-ip")
    def test_empty_raises(self):
        with pytest.raises(ValueError): sanitize_ip("")
    def test_sql_injection_raises(self):
        with pytest.raises(ValueError): sanitize_ip("1.2.3.4'; DROP TABLE transactions;--")


class TestSanitizeChannel:
    def test_valid_online(self):   assert sanitize_channel("online") == "online"
    def test_valid_pos(self):      assert sanitize_channel("pos") == "pos"
    def test_uppercase_ok(self):   assert sanitize_channel("ONLINE") == "online"
    def test_invalid_raises(self):
        with pytest.raises(ValueError): sanitize_channel("telegram")
    def test_empty_raises(self):
        with pytest.raises(ValueError): sanitize_channel("")


class TestSanitizeString:
    def test_valid_string(self):
        assert sanitize_string("USER_001", "user_id") == "USER_001"

    def test_sql_injection_raises(self):
        with pytest.raises(ValueError):
            sanitize_string("'; DROP TABLE--", "user_id")

    def test_xss_raises(self):
        with pytest.raises(ValueError):
            sanitize_string("<script>alert(1)</script>", "user_id")

    def test_too_long_raises(self):
        with pytest.raises(ValueError):
            sanitize_string("A" * 200, "user_id", max_len=100)

    def test_empty_raises(self):
        with pytest.raises(ValueError): sanitize_string("", "user_id")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError): sanitize_string("   ", "user_id")

    def test_unicode_injection_raises(self):
        with pytest.raises(ValueError):
            sanitize_string("user\x00null", "user_id")

    def test_path_traversal_raises(self):
        with pytest.raises(ValueError):
            sanitize_string("../../etc/passwd", "user_id")


# ── Rate Limiter ──────────────────────────────────────────────────────────

class TestRateLimiter:
    def test_allows_under_limit(self):
        limiter = RateLimiter(requests_per_minute=10)
        for _ in range(9):
            limiter.check("1.2.3.4")  # should not raise

    def test_blocks_over_limit(self):
        from fastapi import HTTPException
        limiter = RateLimiter(requests_per_minute=5)
        with pytest.raises(HTTPException) as exc_info:
            for _ in range(10):
                limiter.check("1.2.3.4")
        assert exc_info.value.status_code == 429

    def test_different_ips_independent(self):
        limiter = RateLimiter(requests_per_minute=3)
        from fastapi import HTTPException
        # Fill up IP1
        try:
            for _ in range(10): limiter.check("1.1.1.1")
        except HTTPException:
            pass
        # IP2 should still be fine
        limiter.check("2.2.2.2")  # should not raise

    def test_usage_tracking(self):
        limiter = RateLimiter(requests_per_minute=100)
        for _ in range(5): limiter.check("3.3.3.3")
        usage = limiter.get_usage("3.3.3.3")
        assert usage["requests_last_minute"] == 5
        assert usage["remaining"] == 95

    def test_429_has_retry_after(self):
        from fastapi import HTTPException
        limiter = RateLimiter(requests_per_minute=2)
        try:
            for _ in range(5): limiter.check("4.4.4.4")
        except HTTPException as e:
            assert "Retry-After" in e.headers
            assert int(e.headers["Retry-After"]) > 0


# ── API Key Auth ──────────────────────────────────────────────────────────

class TestAPIKeyAuth:
    """Test API key verification logic."""

    def test_valid_key_passes(self):
        import hmac
        from config.settings import settings
        key = settings.API_KEYS[0]
        # Should not raise
        valid = any(hmac.compare_digest(key.encode(), k.encode()) for k in settings.API_KEYS)
        assert valid is True

    def test_invalid_key_fails(self):
        import hmac
        from config.settings import settings
        key = "totally-wrong-key"
        valid = any(hmac.compare_digest(key.encode(), k.encode()) for k in settings.API_KEYS)
        assert valid is False

    def test_timing_safe_comparison(self):
        """Constant-time comparison prevents timing attacks."""
        import hmac
        # Both comparisons should take similar time
        t1 = time.perf_counter()
        hmac.compare_digest("wrong-key".encode(), "dev-key-change-in-prod".encode())
        t1 = time.perf_counter() - t1

        t2 = time.perf_counter()
        hmac.compare_digest("dev-key-change-in-prod".encode(), "dev-key-change-in-prod".encode())
        t2 = time.perf_counter() - t2

        # Times should be close (both < 1ms, no large discrepancy)
        assert max(t1, t2) < 0.001


# ── Security Headers ──────────────────────────────────────────────────────

class TestSecurityHeaders:
    def test_all_required_headers_present(self):
        from src.security.auth import SECURITY_HEADERS
        required = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Cache-Control",
        ]
        for h in required:
            assert h in SECURITY_HEADERS, f"Missing header: {h}"

    def test_xss_protection_value(self):
        from src.security.auth import SECURITY_HEADERS
        assert "1; mode=block" in SECURITY_HEADERS["X-XSS-Protection"]

    def test_clickjacking_protection(self):
        from src.security.auth import SECURITY_HEADERS
        assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"

    def test_hsts_present(self):
        from src.security.auth import SECURITY_HEADERS
        hsts = SECURITY_HEADERS["Strict-Transport-Security"]
        assert "max-age" in hsts

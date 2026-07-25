"""
API Integration Tests — full HTTP request/response cycle via TestClient.
This closes the coverage gap flagged in the pre-deploy audit
(src/api/main.py previously had 0% test coverage — the riskiest
surface, since it's the actual customer-facing entry point).
"""

from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("API_KEYS", "test-key-for-pytest-only")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-pytest-only-32chars")
os.environ.setdefault("ENABLE_PATHWAY_THREAD", "false")  # no background thread in tests

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

API_KEY = "test-key-for-pytest-only"
HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def valid_tx_payload(**overrides) -> dict:
    payload = dict(
        user_id="TEST_USER_001",
        amount=100.0,
        currency="USD",
        merchant_id="MERCH_001",
        merchant_category="grocery",
        location="US",
        device_id="DEV_001",
        ip_address="192.168.1.1",
        is_international=False,
        is_card_present=True,
        channel="online",
    )
    payload.update(overrides)
    return payload


# ══════════════════════════════════════════════════════════════════════════
# Health & System
# ══════════════════════════════════════════════════════════════════════════


class TestHealthEndpoint:
    def test_health_no_auth_required(self, client):
        r = client.get("/api/v2/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_health_includes_version(self, client):
        r = client.get("/api/v2/health")
        assert "version" in r.json()


# ══════════════════════════════════════════════════════════════════════════
# Authentication
# ══════════════════════════════════════════════════════════════════════════


class TestAuthentication:
    def test_missing_api_key_rejected(self, client):
        r = client.post("/api/v2/transactions/analyze", json=valid_tx_payload())
        assert r.status_code == 401

    def test_invalid_api_key_rejected(self, client):
        r = client.post(
            "/api/v2/transactions/analyze",
            headers={"X-API-Key": "totally-wrong-key"},
            json=valid_tx_payload(),
        )
        assert r.status_code == 403

    def test_valid_api_key_accepted(self, client):
        r = client.post("/api/v2/transactions/analyze", headers=HEADERS, json=valid_tx_payload())
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════
# Transaction Analysis
# ══════════════════════════════════════════════════════════════════════════


class TestAnalyzeEndpoint:
    def test_normal_transaction_allowed(self, client):
        r = client.post(
            "/api/v2/transactions/analyze",
            headers=HEADERS,
            json=valid_tx_payload(amount=50.0),
        )
        body = r.json()
        assert r.status_code == 200
        assert body["decision"] in ("ALLOW", "REVIEW", "BLOCK")
        assert 0.0 <= body["score"] <= 1.0

    def test_extreme_amount_blocks(self, client):
        r = client.post(
            "/api/v2/transactions/analyze",
            headers=HEADERS,
            json=valid_tx_payload(amount=100_000.0, user_id="EXTREME_TEST"),
        )
        body = r.json()
        assert r.status_code == 200
        assert body["decision"] == "BLOCK"

    def test_response_has_required_fields(self, client):
        r = client.post("/api/v2/transactions/analyze", headers=HEADERS, json=valid_tx_payload())
        body = r.json()
        for field in (
            "transaction_id",
            "is_fraud",
            "score",
            "risk_level",
            "decision",
            "reasons",
            "latency_ms",
        ):
            assert field in body

    def test_response_time_header_present(self, client):
        r = client.post("/api/v2/transactions/analyze", headers=HEADERS, json=valid_tx_payload())
        assert "X-Response-Time-Ms" in r.headers

    def test_security_headers_present(self, client):
        r = client.get("/api/v2/health")
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"


# ══════════════════════════════════════════════════════════════════════════
# Input Validation
# ══════════════════════════════════════════════════════════════════════════


class TestInputValidation:
    def test_negative_amount_rejected(self, client):
        r = client.post(
            "/api/v2/transactions/analyze",
            headers=HEADERS,
            json=valid_tx_payload(amount=-100.0),
        )
        assert r.status_code == 422

    def test_zero_amount_rejected(self, client):
        r = client.post(
            "/api/v2/transactions/analyze",
            headers=HEADERS,
            json=valid_tx_payload(amount=0.0),
        )
        assert r.status_code == 422

    def test_invalid_currency_rejected(self, client):
        r = client.post(
            "/api/v2/transactions/analyze",
            headers=HEADERS,
            json=valid_tx_payload(currency="FAKE"),
        )
        assert r.status_code == 422

    def test_invalid_location_rejected(self, client):
        r = client.post(
            "/api/v2/transactions/analyze",
            headers=HEADERS,
            json=valid_tx_payload(location="USA"),  # must be 2-letter
        )
        assert r.status_code == 422

    def test_invalid_ip_rejected(self, client):
        r = client.post(
            "/api/v2/transactions/analyze",
            headers=HEADERS,
            json=valid_tx_payload(ip_address="not-an-ip"),
        )
        assert r.status_code == 422

    def test_invalid_channel_rejected(self, client):
        r = client.post(
            "/api/v2/transactions/analyze",
            headers=HEADERS,
            json=valid_tx_payload(channel="telegram"),
        )
        assert r.status_code == 422

    def test_sql_injection_in_user_id_rejected(self, client):
        r = client.post(
            "/api/v2/transactions/analyze",
            headers=HEADERS,
            json=valid_tx_payload(user_id="'; DROP TABLE transactions;--"),
        )
        assert r.status_code == 422

    def test_xss_in_user_id_rejected(self, client):
        r = client.post(
            "/api/v2/transactions/analyze",
            headers=HEADERS,
            json=valid_tx_payload(user_id="<script>alert(1)</script>"),
        )
        assert r.status_code == 422

    def test_missing_required_field_rejected(self, client):
        payload = valid_tx_payload()
        del payload["user_id"]
        r = client.post("/api/v2/transactions/analyze", headers=HEADERS, json=payload)
        assert r.status_code == 422

    def test_amount_over_max_rejected(self, client):
        r = client.post(
            "/api/v2/transactions/analyze",
            headers=HEADERS,
            json=valid_tx_payload(amount=20_000_000.0),
        )
        assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════
# Query Parameter Bounds (audit fix — limit=-1 must not return 200)
# ══════════════════════════════════════════════════════════════════════════


class TestQueryBounds:
    def test_negative_limit_rejected(self, client):
        r = client.get("/api/v2/transactions/recent?limit=-1", headers=HEADERS)
        assert r.status_code == 422

    def test_zero_limit_rejected(self, client):
        r = client.get("/api/v2/transactions/recent?limit=0", headers=HEADERS)
        assert r.status_code == 422

    def test_excessive_limit_rejected(self, client):
        r = client.get("/api/v2/transactions/recent?limit=999999", headers=HEADERS)
        assert r.status_code == 422

    def test_valid_limit_accepted(self, client):
        r = client.get("/api/v2/transactions/recent?limit=10", headers=HEADERS)
        assert r.status_code == 200

    def test_alerts_negative_limit_rejected(self, client):
        r = client.get("/api/v2/alerts?limit=-5", headers=HEADERS)
        assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════
# Batch Endpoint
# ══════════════════════════════════════════════════════════════════════════


class TestBatchEndpoint:
    def test_batch_scores_multiple(self, client):
        payloads = [valid_tx_payload(user_id=f"BATCH_{i}") for i in range(5)]
        r = client.post("/api/v2/transactions/batch", headers=HEADERS, json=payloads)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 5
        assert len(body["results"]) == 5

    def test_batch_over_limit_rejected(self, client):
        payloads = [valid_tx_payload(user_id=f"OVER_{i}") for i in range(150)]
        r = client.post("/api/v2/transactions/batch", headers=HEADERS, json=payloads)
        assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════
# Stats & Dashboard
# ══════════════════════════════════════════════════════════════════════════


class TestStatsEndpoint:
    def test_stats_returns_valid_structure(self, client):
        client.post("/api/v2/transactions/analyze", headers=HEADERS, json=valid_tx_payload())
        r = client.get("/api/v2/stats", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        for field in (
            "total_transactions",
            "fraud_count",
            "fraud_rate",
            "blocked_count",
            "avg_latency_ms",
        ):
            assert field in body

    def test_stats_requires_auth(self, client):
        r = client.get("/api/v2/stats")
        assert r.status_code == 401


# ══════════════════════════════════════════════════════════════════════════
# Alert Review Workflow
# ══════════════════════════════════════════════════════════════════════════


class TestAlertReview:
    def test_review_alert_workflow(self, client):
        # Create a high-risk transaction that lands in the alert queue
        r = client.post(
            "/api/v2/transactions/analyze",
            headers=HEADERS,
            json=valid_tx_payload(amount=100_000.0, user_id="ALERT_TEST_USER"),
        )
        tx_id = r.json()["transaction_id"]

        # Review it
        r2 = client.post(
            f"/api/v2/alerts/{tx_id}/review",
            headers=HEADERS,
            json={"is_fraud": True, "notes": "Confirmed by test"},
        )
        assert r2.status_code == 200
        assert r2.json()["label"] is True


# ══════════════════════════════════════════════════════════════════════════
# Load — sequential requests
# ══════════════════════════════════════════════════════════════════════════


class TestAPILoad:
    def test_100_sequential_requests_no_errors(self, client):
        errors = 0
        for i in range(100):
            r = client.post(
                "/api/v2/transactions/analyze",
                headers=HEADERS,
                json=valid_tx_payload(user_id=f"LOAD_{i}", amount=50.0 + i),
            )
            if r.status_code != 200:
                errors += 1
        assert errors == 0


# ══════════════════════════════════════════════════════════════════════════
# Security Hardening — request size limits, info disclosure
# ══════════════════════════════════════════════════════════════════════════


class TestRequestSizeLimit:
    """
    Guards a DoS vector: without a body-size cap, a malicious actor could
    send a very large payload and force the server to spend memory/CPU
    buffering and parsing it before any business-logic validation runs.
    """

    def test_oversized_content_length_rejected(self, client):
        # Simulate a client claiming a huge body via Content-Length,
        # without actually needing to transfer gigabytes of real data.
        huge_body = "x" * 100  # small actual body
        r = client.post(
            "/api/v2/transactions/analyze",
            headers={**HEADERS, "Content-Length": "50000000"},  # claims 50MB
            content=huge_body,
        )
        assert r.status_code == 413

    def test_normal_sized_request_accepted(self, client):
        r = client.post("/api/v2/transactions/analyze", headers=HEADERS, json=valid_tx_payload())
        assert r.status_code == 200


class TestHealthEndpointDisclosure:
    """
    Guards against information disclosure: the health endpoint is
    intentionally unauthenticated (monitoring tools can't carry an API
    key), so it must never leak business data (transaction counts, model
    training status) or raw internal exception messages to an anonymous
    caller. That detail now lives behind the authenticated /metrics
    endpoint instead.
    """

    def test_health_does_not_leak_transaction_counts(self, client):
        r = client.get("/api/v2/health")
        body = r.json()
        assert "db_transactions" not in body
        assert "total_analyzed" not in body
        assert "xgb_trained" not in body

    def test_health_returns_minimal_fields_only(self, client):
        r = client.get("/api/v2/health")
        body = r.json()
        assert set(body.keys()) <= {"status", "version", "environment"}

    def test_metrics_requires_auth_and_has_full_detail(self, client):
        # Unauthenticated: rejected
        r = client.get("/api/v2/metrics")
        assert r.status_code == 401

        # Authenticated: full operational detail available here instead
        r2 = client.get("/api/v2/metrics", headers=HEADERS)
        assert r2.status_code == 200
        assert "system" in r2.json()

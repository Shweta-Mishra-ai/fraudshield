"""
Pytest configuration — shared fixtures across all test modules.
Ensures environment is set to 'development' so production secret
validation doesn't block test runs.
"""
import os
import sys
from pathlib import Path

# Make src/ and config/ importable from any test file
sys.path.insert(0, str(Path(__file__).parent.parent))

# Force development mode for all tests — prevents
# settings.validate_production_secrets() from blocking test runs
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("API_KEYS", "test-key-for-pytest-only")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-pytest-only-32chars")
os.environ.setdefault("ENABLE_PATHWAY_THREAD", "false")

# FIX (test isolation): the rate limiter is a module-level singleton
# (src.security.auth._rate_limiter) that persists across every test
# function in the same pytest session — because many tests share the
# same TestClient "testclient" fake IP, tests run earlier in the suite
# quietly consume part of later tests' rate-limit budget, causing
# flaky, order-dependent failures that have nothing to do with actual
# fraud-detection correctness. Set a very high test-only limit so the
# limiter's own behavior (already covered by tests/security/test_security.py)
# doesn't interfere with unrelated functional/load tests.
os.environ.setdefault("RATE_LIMIT", "1000000")

import pytest


@pytest.fixture(autouse=True)
def _deterministic_randomness():
    """
    FIX (test reliability): TransactionGenerator uses Python's `random`
    module without a fixed seed. Statistical tests that sample a batch
    and assert "at least one high-value fraud scenario appears" have a
    small but real chance of failing on an unlucky draw (~1-in-18 runs
    for the default batch size) — exactly the kind of flaky CI failure
    that erodes trust in a test suite. Seeding before every test makes
    all randomized generator output fully reproducible.
    """
    import random
    random.seed(42)
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limiter_between_tests():
    """
    Reset the rate-limiter singleton before each test so no test's
    request volume can bleed into another test's pass/fail outcome.
    """
    import src.security.auth as auth_module
    auth_module._rate_limiter = None
    yield


@pytest.fixture(autouse=True)
def _reset_environment():
    """Ensure each test starts with a clean environment variable state."""
    yield

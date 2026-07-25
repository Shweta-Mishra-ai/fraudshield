# 🛡️ FraudShield — Real-Time Fraud Detection API

**Production-grade fraud detection engine.** Rule engine + ML ensemble + graph analytics + real-time streaming, wrapped in a secured REST API with sub-10ms decisions.

[![API CI](https://github.com/Shweta-Mishra-ai/fraudshield/actions/workflows/api-ci.yml/badge.svg)](../../.github/workflows/api-ci.yml)
[![Tests](https://img.shields.io/badge/tests-173%20passing-brightgreen)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-78%25-yellow)](tests/)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](requirements.txt)
[![FastAPI](https://img.shields.io/badge/FastAPI-secured-009688)](src/api/main.py)
[![License](https://img.shields.io/badge/license-MIT-green)](#license)

---

## Table of Contents

- [What This Is](#what-this-is)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Fraud Decision Engine](#fraud-decision-engine)
- [Testing](#testing)
- [Error Handling and Resilience](#error-handling-and-resilience)
- [Load Handling and Performance](#load-handling-and-performance)
- [Input Validation](#input-validation)
- [Security](#security)
- [CI/CD](#cicd)
- [Deployment](#deployment)
- [Configuration Reference](#configuration-reference)
- [Known Limitations](#known-limitations)
- [Contributing and Branching Workflow](#contributing-and-branching-workflow)
- [License](#license)

---

## What This Is

FraudShield scores financial transactions for fraud risk in **real time** (single-digit milliseconds) using a three-layer decision engine:

| Layer | Weight | What It Catches |
|---|---|---|
| **Rule Engine** (9 rules) | 40% | Deterministic patterns — velocity abuse, impossible travel, shared-device rings, high-risk merchants |
| **ML Ensemble** (XGBoost + IsolationForest) | 45% | Statistical anomalies and learned fraud patterns, with SHAP explainability |
| **Graph Engine** (NetworkX) | 15% | Fraud rings via shared device/IP/merchant relationships |

A transaction is classified **ALLOW**, **REVIEW**, or **BLOCK**. Critically, any rule with 100% certainty (e.g. amount over an absolute hard limit) forces BLOCK regardless of the ML/graph opinion — a probabilistic blend can never water down a deterministic business rule. See [Fraud Decision Engine](#fraud-decision-engine) for the full rationale.

---

## Architecture

```
+--------------------------------------------------------------------+
|                         FraudShield API                            |
|                                                                      |
|   HTTP Request                                                      |
|        |                                                            |
|        v                                                            |
|   Security Middleware:                                              |
|   API Key Auth --> Rate Limiter --> Input Validation                |
|   (hmac compare)   (sliding window)  (Pydantic + sanitizers)        |
|        |                                                            |
|        v                                                            |
|   FraudDetector (orchestrator)                                      |
|     1. FeatureEngineer  -> 22 engineered features                   |
|     2. RuleEngine       -> 9 deterministic rules                    |
|     3. MLEnsemble       -> XGBoost + IsolationForest                |
|     4. GraphEngine      -> fraud ring detection                     |
|     5. Ensemble blend + critical-rule hard override                 |
|        |                                                            |
|        v                                                            |
|   FraudResult { decision, score, reasons, latency_ms }               |
|        |                                                            |
|        v                                                            |
|   SQLite / PostgreSQL  (PII fields hashed before storage)            |
|                                                                      |
|   Pathway streaming pipeline runs as a background thread             |
|   inside this same process -- see "Why in-process?" below.           |
+--------------------------------------------------------------------+
```

### Why does Pathway run in-process rather than as a separate worker?

Render's free tier does **not** share a filesystem between separate services. If the streaming pipeline ran as its own worker service, the CSV files this API writes would be invisible to it on a different container — the whole pipeline would silently do nothing. Running Pathway as a daemon thread inside the same process guarantees both share the same local disk, so streaming genuinely works on a single free-tier instance. This is a deliberate architectural decision, not an oversight — see `src/api/main.py::lifespan()`.

---

## Quick Start

### Prerequisites
- Python 3.11 or 3.12
- pip

### Install and Run Locally

```bash
git clone https://github.com/Shweta-Mishra-ai/fraudshield.git
cd fraudshield/apps/api

pip install -r requirements.txt
cp .env.example .env
uvicorn src.api.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for interactive API documentation.

### Run the Dashboard (analyst tool)

```bash
streamlit run dashboard/app.py
```

### Run With Docker

```bash
docker build -t fraudshield-api .
docker run -p 8000:8000 \
  -e API_KEYS=your-dev-key \
  -e JWT_SECRET=your-dev-secret-minimum-32-characters \
  -e ENVIRONMENT=development \
  fraudshield-api
```

---

## API Reference

**Base URL (local):** `http://localhost:8000`
**Auth:** every endpoint except `/api/v2/health` requires an `X-API-Key` header.

### Score a Transaction

```
POST /api/v2/transactions/analyze
X-API-Key: your-api-key
Content-Type: application/json

{
  "user_id": "USER_0042",
  "amount": 5000.00,
  "currency": "USD",
  "merchant_id": "MERCH_007",
  "merchant_category": "crypto",
  "location": "RU",
  "device_id": "DEV_NEW_001",
  "ip_address": "203.0.113.42",
  "is_international": true,
  "is_card_present": false,
  "channel": "online"
}
```

**Response:**

```json
{
  "transaction_id": "a3f8c2d1-...",
  "is_fraud": true,
  "score": 0.95,
  "risk_level": "CRITICAL",
  "decision": "BLOCK",
  "reasons": [
    "Amount $5,000 exceeds critical threshold $10,000",
    "Merchant category 'crypto' is very high risk (score 0.90)"
  ],
  "top_features": [
    {"feature": "amount_zscore", "shap_value": 0.312}
  ],
  "scores": {"rule": 1.0, "ml": 0.25, "graph": 0.0},
  "latency_ms": 7.8,
  "model_version": "2.1.0"
}
```

> **Note:** `is_fraud` is `true` only when `decision == "BLOCK"` (confirmed, high-confidence fraud). A `REVIEW` decision means "ambiguous, needs a human" — it is intentionally **not** flagged as `is_fraud: true`, so downstream dashboards and stats never conflate "flagged for review" with "confirmed fraud."

### All Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET  | `/api/v2/health` | none | Liveness/readiness probe |
| POST | `/api/v2/transactions/analyze` | required | Score one transaction |
| POST | `/api/v2/transactions/batch` | required | Score up to 100 transactions |
| POST | `/api/v2/transactions/stream` | required | Feed the Pathway streaming pipeline |
| GET  | `/api/v2/transactions/recent` | required | Recent transaction feed |
| GET  | `/api/v2/alerts` | required | Unreviewed REVIEW/BLOCK queue |
| GET  | `/api/v2/alerts/stream` | required | Real-time alerts from Pathway |
| POST | `/api/v2/alerts/{id}/review` | required | Analyst feedback (feeds retraining) |
| GET  | `/api/v2/stats` | required | Dashboard KPIs |
| GET  | `/api/v2/users/{id}/history` | required | Per-user transaction history |
| GET  | `/api/v2/fraud-rings` | required | Graph-detected fraud rings |
| GET  | `/api/v2/metrics` | required | System/model metrics |

Full interactive schema: `/docs` (Swagger) or `/redoc`.

---

## Fraud Decision Engine

### The 9 Rules

| Rule | Trigger | Notes |
|---|---|---|
| High Amount | over $5,000 elevated, over $10,000 critical (hard BLOCK) | The $10k tier is a business-certain override — see below |
| Amount Z-Score | over 2.5 sigma / over 4 sigma above user's own average | Skipped entirely for brand-new users (no history to compare against) |
| Velocity Abuse | over 10 tx/hour or over 30 tx/24h | |
| New Country | Established user + new country + amount over $500 | New users are not flagged for their first-ever location |
| New Device | Established user + new device (+ new country = higher severity) | New users are not flagged for their first-ever device |
| Night-Time High Value | over $2,000 between 00:00-06:00 UTC | |
| High-Risk Merchant | Crypto / gambling / wire-transfer categories | |
| Shared Device/IP Ring | Device shared by 3+ users, or IP by 5+ | |
| Card-Not-Present + High-Risk | CNP transaction on a high-risk merchant category | |

### Critical-Rule Hard Override

This is the single most important correctness guarantee in the system. Early in development, a $100,000 transaction on a brand-new account only reached a REVIEW-level score (around 0.40) because the weighted ensemble blend (`0.40 x rule + 0.45 x ml + 0.15 x graph`) capped a 100%-certain rule violation's contribution at 40% — and a first-time user naturally has no ML/graph signal to make up the difference.

**Fix:** any `RuleResult` marked `critical=True` (currently: the $10,000+ absolute amount threshold) forces the final decision to `BLOCK` and the score to at least `0.95`, regardless of what the ML and graph layers say. A deterministic, business-certain signal must never be diluted by a probabilistic average. See `src/core/detector.py` and `tests/unit/test_critical_fixes.py::TestCriticalOverride`.

### Cold-Start Handling

New users' first transactions naturally look "new" on every dimension (new device, new location, no amount history). Without special handling, this causes a false-positive epidemic — in early testing, 100% of first-time users were flagged for REVIEW. Fixed by requiring rules to check account maturity (`txn_count_24h`) before firing on "new device"/"new location" signals alone. Verified in CI: new-user REVIEW rate stays under 10% across randomized batches (`tests/unit/test_critical_fixes.py::TestColdStartRegression`).

---

## Testing

**178 tests, zero known flaky tests, approximately 78% code coverage** (95-99% on all core fraud-decision modules).

```bash
# Full suite
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov=config --cov-report=term-missing

# Fast smoke test (no pytest needed)
python run_tests.py
```

| Suite | File | What It Covers |
|---|---|---|
| Unit | `tests/unit/test_core.py` | Models, features, rules, graph, detector, generator |
| Unit | `tests/unit/test_critical_fixes.py` | Regression guards for every bug found in the pre-deploy audit |
| Integration | `tests/integration/test_integration.py` | Storage, end-to-end scoring flow, Pathway CSV output |
| Integration | `tests/integration/test_api.py` | Full HTTP request/response cycle via `TestClient` — auth, validation, query bounds, batch, alerts workflow |
| Security | `tests/security/test_security.py` | Input sanitization, rate limiting, API key auth, security headers |

### Reproducibility

All randomized test data (via `TransactionGenerator`) is seeded (`random.seed(42)` in `tests/conftest.py`), so the suite produces identical results on every run — no flaky, order-dependent failures. The rate limiter, which is a module-level singleton, is explicitly reset between tests to prevent one test's request volume from silently affecting another's pass/fail outcome.

### Load / Stress Testing

`tests/unit/test_critical_fixes.py::TestLoadHandling` runs 1,000 randomized transactions through the full detection pipeline and requires: zero crashes, every score within `[0.0, 1.0]`, p95 latency under 500ms, and SQLite storage surviving 200 rapid sequential writes.

CI additionally runs a dedicated 1,000-transaction load job and a live Docker container health check on every push.

---

## Error Handling and Resilience

- **Fail-open by design:** if any internal component raises (feature extraction, ML scoring, graph lookup), `FraudDetector.analyze()` catches it, logs the error, and returns a safe `ALLOW` decision rather than crashing the request or blocking a legitimate customer on a system fault.
- **Global exception handler:** any unhandled exception at the API layer returns a structured `500` with a request ID for tracing — never a raw stack trace to the client.
- **Rule-level isolation:** a single broken/misbehaving rule cannot crash the rule engine; each rule's exceptions are caught individually and logged, and evaluation continues for the rest.
- **Idempotent storage:** re-saving the same transaction (e.g. on retry) does not create duplicate rows (`INSERT OR REPLACE`).
- **Graceful ML degradation:** if XGBoost/SHAP are not installed or no trained model file exists, the ensemble automatically falls back to IsolationForest + rules — no crash, clearly logged.
- **Graceful streaming degradation:** if the `pathway` package is not installed, a pure-Python polling fallback with an identical interface takes over automatically.

---

## Load Handling and Performance

| Metric | Value |
|---|---|
| Median detection latency | under 10ms |
| p95 latency (1,000-tx load test) | under 500ms |
| Verified throughput (single instance) | 1,000 transactions processed with zero crashes in CI |
| Rate limit (default) | 100 requests/minute per IP, sliding window, 429 + Retry-After header |
| Memory safety | Graph engine capped at 100,000 nodes with FIFO eviction — prevents unbounded growth from crashing a long-running instance |

---

## Input Validation

Every field on every write endpoint is validated before it reaches business logic:

| Field | Validation |
|---|---|
| `amount` | Must be greater than 0 and at most $10,000,000; rounded to 2 decimal places |
| `currency` | Must be one of 14 whitelisted ISO codes |
| `location` | Must be a 2-letter ISO-3166 country code |
| `ip_address` | Parsed with Python's stdlib `ipaddress` module (not regex) — rejects malformed and injection-laced values |
| `merchant_category` | Normalized against a whitelist; unrecognized values fall back to `"unknown"` rather than being rejected outright |
| `user_id` / `merchant_id` / `device_id` | Alphanumeric + dash/underscore/dot only; blocks path traversal, null bytes, SQL/XSS payloads |
| `channel` | Must be one of `online / pos / atm / mobile / web` |
| Pagination `limit` params | Bounded server-side with `Query(ge=1, le=N)` — a request like `?limit=-1` returns `422`, never silently succeeds |

All validators are covered by dedicated tests in `tests/security/test_security.py` and exercised end-to-end via HTTP in `tests/integration/test_api.py`.

---

## Security

| Control | Implementation |
|---|---|
| Authentication | `X-API-Key` header, compared with `hmac.compare_digest` (timing-attack resistant) |
| Rate limiting | Sliding-window limiter per IP, configurable via `RATE_LIMIT` env var |
| PII protection | `ip_address` and `device_id` are SHA-256 hashed with a server-side salt before being written to storage — raw values are never persisted, while fraud-ring matching (same device maps to same hash) still works |
| SQL injection | 100% parameterized queries; no string-formatted SQL anywhere |
| XSS / path traversal | Blocked at the input-sanitization layer before reaching any handler |
| Secure defaults enforcement | `Settings.validate_production_secrets()` makes the API refuse to start in production if the API key or JWT secret is left at an insecure placeholder value |
| Security headers | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Strict-Transport-Security`, `Referrer-Policy`, `Permissions-Policy` on every response |
| CORS | Explicit allow-list via `ALLOWED_ORIGINS` — no wildcard default |
| Request size limits | Requests over 1MB are rejected via `Content-Length` check **before** JSON parsing — prevents large-payload DoS attacks from consuming server memory/CPU |
| Info disclosure | The unauthenticated `/health` endpoint returns only `status`/`version`/`environment` — no transaction counts, model status, or raw exception messages. Full operational detail is only available via the authenticated `/metrics` endpoint |
| Docs exposure | `/docs` and `/redoc` can be fully disabled in production via `ENABLE_DOCS=false` |

---

## CI/CD

Every push and pull request runs the full pipeline (`.github/workflows/ci.yml`):

1. **Lint** — `black --check` and static analysis
2. **Test matrix** — full pytest suite on Python 3.11 and 3.12, with coverage upload
3. **Dependency audit** — `pip-audit` against `requirements.txt`
4. **Load test** — 1,000-transaction stress run, zero crashes required
5. **Docker build verification** — builds the production image and hits `/api/v2/health` inside a running container

A pull request cannot be merged with a red CI run.

---

## Deployment

### Render (recommended, free tier compatible)

```
1. Push to GitHub, then in Render:
   New -> Web Service -> connect this repo
   Runtime: Docker
   Health check path: /api/v2/health

2. Set environment variables in the Render dashboard (never commit these):
   API_KEYS         = generate with: python -c "import secrets; print(secrets.token_hex(24))"
   JWT_SECRET        = generate with: python -c "import secrets; print(secrets.token_hex(32))"
   ALLOWED_ORIGINS   = https://your-frontend-domain.com
   ENVIRONMENT       = production
   ENABLE_DOCS       = false   (once you have real customers)
```

The monorepo root's `render.yaml` sets `rootDir: apps/api`, so Render always builds from this folder regardless of what else is added elsewhere in the repo — see `/docs/ARCHITECTURE.md` at the repo root for why this never needs reconfiguring. It defines the service as a single web service; Pathway streaming runs in-process (see Architecture above), so no second worker service is needed or recommended on the free tier.

### Manual / any host

```bash
docker build -t fraudshield-api .
docker run -d -p 8000:8000 \
  -e API_KEYS=... -e JWT_SECRET=... -e ENVIRONMENT=production \
  fraudshield-api
```

---

## Configuration Reference

All settings are environment-variable driven (`config/settings.py`). See `.env.example` for the full local-development template.

| Variable | Default | Notes |
|---|---|---|
| `ENVIRONMENT` | `production` | `development` skips secret validation |
| `API_KEYS` | none | Comma-separated list; must be overridden in production |
| `JWT_SECRET` | none | Minimum 32 characters; must be overridden in production |
| `RATE_LIMIT` | `100` | Requests per minute per IP |
| `ALLOWED_ORIGINS` | localhost only | Comma-separated allow-list |
| `ENABLE_DOCS` | `true` | Set `false` to hide `/docs` and `/redoc` |
| `DB_PATH` | `data/fraud.db` | SQLite path; ignored if `DATABASE_URL` is set (PostgreSQL) |
| `DATABASE_URL` | none | If set, storage automatically uses PostgreSQL instead of SQLite |
| `PATHWAY_MODE` | `streaming` | `streaming` (continuous) or `static` (one-shot, for testing) |
| `ENABLE_PATHWAY_THREAD` | `true` | Runs the streaming pipeline as a background thread on API startup |

---

## Known Limitations

Honesty matters more than marketing here:

- **Render free-tier disk is ephemeral.** SQLite data and Pathway CSV/JSONL files reset on redeploy or extended inactivity. For durable production storage, set `DATABASE_URL` to a managed PostgreSQL instance.
- **XGBoost ships untrained by default.** Out of the box, the ML layer runs on IsolationForest heuristics; training on a real labeled dataset (e.g. IEEE-CIS) is a manual step (`scripts/train_xgboost.py`) that meaningfully improves precision/recall.
- **Single-instance state.** Feature history and the fraud graph live in-process. Horizontally scaling to multiple instances requires externalizing this state (Redis is the natural next step) — currently out of scope for the free-tier deployment target.
- **`pathway` is a heavy dependency.** Installing it can slow down cold builds on constrained CI/deploy environments; a pure-Python polling fallback activates automatically if it is unavailable.

---

## Contributing and Branching Workflow

```bash
git checkout -b feature/your-change
# ... make changes ...
python run_tests.py          # fast sanity check
pytest tests/ -v             # full suite
black --check src/ config/   # lint (must be clean)

git add -A
git commit -m "feat: description of your change"
git push origin feature/your-change
# open a Pull Request -- CI must pass before merge
```

Merging into `main` should always be done via Pull Request, never a direct push, so CI has a chance to catch regressions before they reach production.

---

## License

MIT License — see `LICENSE` for details.

---

## Author

**Shweta Mishra** — Python Developer and AI/ML Engineer

[LinkedIn](https://www.linkedin.com/in/shweta-mishra-ai) | [GitHub](https://github.com/Shweta-Mishra-ai)

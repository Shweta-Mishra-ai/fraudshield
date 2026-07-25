"""
Production FastAPI — Fraud Detection API v2.1
Fixes from audit:
  - limit params bounded with Query(ge=1, le=N)
  - currency + merchant_category validated
  - docs disabled in prod via ENABLE_DOCS setting
  - production secrets validated at startup
  - CORS no longer defaults to *
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field, field_validator

from config.settings import settings
from src.core.detector import FraudDetector
from src.core.models import Transaction
from src.core.storage import FraudStorage
from src.security.auth import (
    SECURITY_HEADERS,
    rate_limit_middleware,
    sanitize_amount,
    sanitize_channel,
    sanitize_currency,
    sanitize_ip,
    sanitize_location,
    sanitize_merchant_category,
    sanitize_string,
    verify_api_key,
)
from src.streaming.pathway_pipeline import write_transactions_to_csv

logger = logging.getLogger(__name__)

# ── Singletons (populated by lifespan handler below) ───────────────────────
_detector: Optional[FraudDetector] = None
_storage: Optional[FraudStorage] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Modern FastAPI lifespan handler (replaces the deprecated @app.on_event
    decorator). Code before `yield` runs on startup; code after `yield`
    runs on graceful shutdown.
    """
    global _detector, _storage

    # Validate secrets before accepting traffic
    try:
        settings.validate_production_secrets()
    except RuntimeError as exc:
        logger.critical(str(exc))
        raise SystemExit(1) from exc

    os.makedirs("data/transactions", exist_ok=True)
    os.makedirs("data/alerts", exist_ok=True)

    _storage = FraudStorage(db_path=settings.DB_PATH)

    # Auto-load trained XGBoost model if available
    try:
        from src.ml.ensemble import load_saved_model

        ensemble = load_saved_model("data/models/xgboost_model.json")
        _detector = FraudDetector(ml_ensemble=ensemble)
        if ensemble.xgb_ready:
            logger.info("XGBoost model loaded — full ML ensemble active")
        else:
            logger.info("No trained model — using IsoForest + rules")
    except Exception as exc:
        logger.warning("Model load failed (non-fatal): %s", exc)
        _detector = FraudDetector()

    # Hydrate with historical transactions
    try:
        tx_list = _storage.get_all_transactions()
        if tx_list:
            _detector.hydrate(tx_list)
            logger.info("Hydrated with %d historical transactions", len(tx_list))
    except Exception as exc:
        logger.warning("Hydration failed (non-fatal): %s", exc)

    # ── Pathway streaming: run IN-PROCESS, not a separate service ─────────
    # FIX (critical): Render's free tier does NOT share a filesystem
    # between separate services (API web service vs a worker service run
    # on different containers). If Pathway ran as a separate service, the
    # CSV files written by this API would be invisible to it — the whole
    # streaming pipeline would silently do nothing. Running it as a
    # background thread inside this same process guarantees they share
    # the same local disk, so it actually works.
    if os.getenv("ENABLE_PATHWAY_THREAD", "true").lower() == "true":
        try:
            import threading
            from src.streaming.pathway_pipeline import run_pathway_pipeline

            def _run_pipeline_safely():
                try:
                    run_pathway_pipeline(
                        input_dir=settings.PATHWAY_INPUT_DIR,
                        alerts_dir=settings.PATHWAY_ALERTS_DIR,
                        mode=settings.PATHWAY_MODE,
                    )
                except Exception as exc:
                    logger.error("Pathway background thread crashed: %s", exc, exc_info=True)

            thread = threading.Thread(target=_run_pipeline_safely, daemon=True)
            thread.start()
            logger.info("Pathway streaming pipeline started in background thread")
        except Exception as exc:
            logger.warning("Could not start Pathway thread (non-fatal): %s", exc)

    logger.info("API v%s started (%s)", settings.APP_VERSION, settings.ENVIRONMENT)

    yield  # ── application runs here ──────────────────────────────────────

    # ── Graceful shutdown ───────────────────────────────────────────────
    logger.info("API shutting down gracefully")


# ── App ───────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Production-grade real-time fraud detection — "
        "ML Ensemble + Rule Engine + Graph Analytics + Pathway Streaming."
    ),
    version=settings.APP_VERSION,
    # FIX (audit #8): disable docs in production unless explicitly enabled
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
    lifespan=lifespan,
)

# FIX (audit #8): CORS no longer defaults to *
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
    allow_credentials=False,
)


def get_detector() -> FraudDetector:
    if _detector is None:
        raise HTTPException(status_code=503, detail="Detector not ready")
    return _detector


def get_storage() -> FraudStorage:
    if _storage is None:
        raise HTTPException(status_code=503, detail="Storage not ready")
    return _storage


# ── Middleware ────────────────────────────────────────────────────────────

MAX_REQUEST_BODY_BYTES = (
    1_000_000  # 1 MB — generous for a 100-item batch, far too small for a DoS payload
)


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """
    FIX (security hardening): reject oversized request bodies via the
    Content-Length header BEFORE FastAPI/Pydantic attempts to buffer and
    parse them. Without this, a malicious actor could send a very large
    JSON payload (megabytes of junk, or a batch array with far more than
    100 items) and force the server to spend memory/CPU parsing it before
    our own `len(requests) > 100` business-logic check ever runs. This is
    the same class of protection nginx's `client_max_body_size` provides
    at the reverse-proxy layer — enforced here too since this API may run
    directly behind Render's edge without a custom proxy in front of it.
    """
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_BODY_BYTES:
        return JSONResponse(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            content={"error": "Request body too large", "max_bytes": MAX_REQUEST_BODY_BYTES},
        )
    return await call_next(request)


@app.middleware("http")
async def security_and_timing(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = round((time.perf_counter() - t0) * 1000, 2)
    for k, v in SECURITY_HEADERS.items():
        response.headers[k] = v
    response.headers["X-Response-Time-Ms"] = str(ms)
    response.headers["X-API-Version"] = settings.APP_VERSION
    return response


@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "request_id": str(uuid.uuid4())},
    )


# ── Pydantic Schemas ──────────────────────────────────────────────────────


class TransactionRequest(BaseModel):
    transaction_id: Optional[str] = None
    user_id: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., gt=0, le=10_000_000)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    merchant_id: str = Field(..., min_length=1, max_length=100)
    merchant_category: str = Field(default="unknown", max_length=50)
    location: str = Field(..., min_length=2, max_length=2)
    device_id: str = Field(..., min_length=1, max_length=100)
    ip_address: str = Field(..., min_length=7, max_length=45)
    is_international: bool = False
    is_card_present: bool = True
    channel: str = Field(default="online", max_length=20)

    @field_validator("amount")
    @classmethod
    def v_amount(cls, v):
        return sanitize_amount(v)

    @field_validator("location")
    @classmethod
    def v_location(cls, v):
        return sanitize_location(v)

    @field_validator("ip_address")
    @classmethod
    def v_ip(cls, v):
        return sanitize_ip(v)

    @field_validator("channel")
    @classmethod
    def v_channel(cls, v):
        return sanitize_channel(v)

    @field_validator("currency")
    @classmethod
    def v_currency(cls, v):
        return sanitize_currency(v)

    @field_validator("merchant_category")
    @classmethod
    def v_merchant_cat(cls, v):
        return sanitize_merchant_category(v)

    @field_validator("user_id", "merchant_id", "device_id")
    @classmethod
    def v_ids(cls, v):
        return sanitize_string(v, "id field", max_len=100)

    def to_transaction(self) -> Transaction:
        return Transaction(
            transaction_id=self.transaction_id or str(uuid.uuid4()),
            user_id=self.user_id,
            amount=self.amount,
            currency=self.currency,
            timestamp=time.time(),
            merchant_id=self.merchant_id,
            merchant_category=self.merchant_category,
            location=self.location,
            device_id=self.device_id,
            ip_address=self.ip_address,
            is_international=self.is_international,
            is_card_present=self.is_card_present,
            channel=self.channel,
        )


class AnalystReviewRequest(BaseModel):
    is_fraud: bool
    notes: str = Field(default="", max_length=1000)


# ── Shared deps ───────────────────────────────────────────────────────────

SecureDeps = [Depends(verify_api_key), Depends(rate_limit_middleware)]


# ── System endpoints (no auth) ────────────────────────────────────────────


@app.get("/api/v2/health", tags=["System"])
async def health():
    """
    Liveness + readiness probe — used by Render health checks.

    FIX (security hardening): this endpoint is intentionally unauthenticated
    (health checkers can't be expected to carry an API key), which means it
    must never reveal anything beyond "is the service up". Previously it
    returned transaction counts, model training status, and — on failure —
    the raw exception message, all to any anonymous caller. Detailed
    operational diagnostics now live behind /api/v2/metrics, which
    requires a valid API key.
    """
    try:
        get_detector()
        get_storage()
        return {
            "status": "healthy",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        }
    except Exception as exc:
        logger.error("Health check failed: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy"},  # no internal details leaked
        )


@app.get("/api/v2/metrics", tags=["System"], dependencies=[Depends(verify_api_key)])
async def metrics():
    det = get_detector()
    return {
        "system": det.get_system_status(),
        "graph": det.graph.get_stats(),
        "model_version": settings.MODEL_VERSION,
        "timestamp": time.time(),
    }


# ── Transaction endpoints ─────────────────────────────────────────────────


@app.post("/api/v2/transactions/analyze", tags=["Transactions"], dependencies=SecureDeps)
async def analyze_transaction(req: TransactionRequest):
    """Score a single transaction. Returns ALLOW / REVIEW / BLOCK + explanation."""
    detector = get_detector()
    storage = get_storage()
    tx = req.to_transaction()
    result = detector.analyze(tx)
    try:
        storage.save(tx, result)
    except Exception as exc:
        logger.error("Storage failed for %s: %s", tx.transaction_id, exc)
    return result.to_dict()


@app.post("/api/v2/transactions/batch", tags=["Transactions"], dependencies=SecureDeps)
async def analyze_batch(requests: List[TransactionRequest]):
    """Score up to 100 transactions in one call."""
    if len(requests) > settings.BATCH_SIZE_LIMIT:
        raise HTTPException(
            status_code=422,
            detail=f"Batch size cannot exceed {settings.BATCH_SIZE_LIMIT}",
        )
    detector = get_detector()
    storage = get_storage()
    results = []
    for req in requests:
        tx = req.to_transaction()
        result = detector.analyze(tx)
        try:
            storage.save(tx, result)
        except Exception as exc:
            logger.warning("Batch storage failed for %s: %s", tx.transaction_id, exc)
        results.append(result.to_dict())

    fraud_count = sum(1 for r in results if r["is_fraud"])
    return {
        "total": len(results),
        "fraud_found": fraud_count,
        "fraud_rate": round(fraud_count / len(results) * 100, 2) if results else 0,
        "results": results,
    }


@app.post("/api/v2/transactions/stream", tags=["Streaming"], dependencies=SecureDeps)
async def stream_transactions(requests: List[TransactionRequest]):
    """Write transactions to Pathway input directory for real-time scoring."""
    if len(requests) > settings.BATCH_SIZE_LIMIT:
        raise HTTPException(status_code=422, detail="Max 100 per stream call")
    txns = [req.to_transaction() for req in requests]
    try:
        filename = write_transactions_to_csv(txns, "data/transactions")
        return {
            "status": "queued",
            "count": len(txns),
            "file": os.path.basename(filename),
            "message": "Pathway pipeline will score these within 500ms",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Stream write failed: {exc}")


@app.get("/api/v2/transactions/recent", tags=["Transactions"], dependencies=SecureDeps)
async def get_recent(
    # FIX (audit #11): bounded with ge=1, le=500 — rejects limit=-1
    limit: int = Query(
        default=50, ge=1, le=500, description="Number of recent transactions to return"
    ),
):
    return get_storage().get_recent(limit)


# ── Alert endpoints ───────────────────────────────────────────────────────


@app.get("/api/v2/alerts", tags=["Alerts"], dependencies=SecureDeps)
async def get_alerts(
    limit: int = Query(default=20, ge=1, le=200, description="Max alerts to return"),
):
    """Unreviewed REVIEW/BLOCK alerts ordered by risk score."""
    return get_storage().get_alerts(limit)


@app.get("/api/v2/alerts/stream", tags=["Streaming", "Alerts"], dependencies=SecureDeps)
async def get_stream_alerts(
    limit: int = Query(default=50, ge=1, le=500),
):
    """Read real-time alerts written by Pathway pipeline."""
    alerts_path = Path("data/alerts/alerts.jsonl")
    if not alerts_path.exists():
        return {"alerts": [], "source": "pathway", "message": "No alerts yet"}
    alerts = []
    try:
        lines = alerts_path.read_text(encoding="utf-8").strip().split("\n")
        for line in reversed(lines):
            if line.strip():
                try:
                    alerts.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            if len(alerts) >= limit:
                break
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read alerts: {exc}")
    return {"alerts": alerts, "count": len(alerts), "source": "pathway_stream"}


@app.post("/api/v2/alerts/{transaction_id}/review", tags=["Alerts"], dependencies=SecureDeps)
async def review_alert(transaction_id: str, body: AnalystReviewRequest):
    """Record analyst decision — feeds model retraining pipeline."""
    safe_id = sanitize_string(transaction_id, "transaction_id", max_len=100)
    try:
        get_storage().update_analyst_review(safe_id, body.is_fraud, body.notes)
        return {"status": "ok", "transaction_id": safe_id, "label": body.is_fraud}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Dashboard / Stats ─────────────────────────────────────────────────────


@app.get("/api/v2/stats", tags=["Dashboard"], dependencies=SecureDeps)
async def get_stats():
    """Aggregate KPIs: fraud rate, latency, pending reviews."""
    return get_storage().get_stats()


@app.get("/api/v2/users/{user_id}/history", tags=["Users"], dependencies=SecureDeps)
async def get_user_history(
    user_id: str,
    limit: int = Query(default=30, ge=1, le=200),
):
    safe_id = sanitize_string(user_id, "user_id", max_len=100)
    return get_storage().get_user_history(safe_id, limit)


@app.get("/api/v2/fraud-rings", tags=["Dashboard"], dependencies=SecureDeps)
async def get_fraud_rings():
    det = get_detector()
    return {"rings": det.graph.detect_rings(), "graph_stats": det.graph.get_stats()}

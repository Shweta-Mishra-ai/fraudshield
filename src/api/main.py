"""
FastAPI REST API for the Fraud Detection System.

Endpoints:
  POST /api/v1/transactions/analyze   — score a single transaction
  POST /api/v1/transactions/batch     — score up to 100 at once
  GET  /api/v1/transactions/recent    — recent transactions
  GET  /api/v1/alerts                 — unreviewed high-risk alerts
  POST /api/v1/alerts/{id}/review     — analyst feedback
  GET  /api/v1/stats                  — dashboard KPIs
  GET  /api/v1/users/{id}/history     — per-user transaction history
  GET  /api/v1/health                 — liveness probe
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from ..core.detector import FraudDetector
from ..core.models import Transaction
from ..core.storage import FraudStorage

logger = logging.getLogger(__name__)

# ── App setup ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Fraud Detection API",
    description="Real-time transaction fraud scoring with ML ensemble + rule engine",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singletons (initialized at startup) ───────────────────────────────────
_detector: Optional[FraudDetector] = None
_storage:  Optional[FraudStorage]  = None


@app.on_event("startup")
async def startup():
    global _detector, _storage
    _detector = FraudDetector()
    _storage  = FraudStorage()
    logger.info("FraudDetector and Storage initialized")


def get_detector() -> FraudDetector:
    if _detector is None:
        raise HTTPException(status_code=503, detail="Detector not initialized")
    return _detector

def get_storage() -> FraudStorage:
    if _storage is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    return _storage


# ── Request / Response schemas ────────────────────────────────────────────

class TransactionRequest(BaseModel):
    transaction_id:   Optional[str] = None
    user_id:          str = Field(..., min_length=1, max_length=100)
    amount:           float = Field(..., gt=0, le=1_000_000)
    currency:         str = Field(default="USD", max_length=3)
    merchant_id:      str = Field(..., min_length=1, max_length=100)
    merchant_category: str = Field(default="unknown", max_length=50)
    location:         str = Field(..., min_length=2, max_length=2)
    device_id:        str = Field(..., min_length=1, max_length=100)
    ip_address:       str = Field(..., min_length=7, max_length=45)
    is_international: bool = False
    is_card_present:  bool = True
    channel:          str = Field(default="online", max_length=20)

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("amount must be positive")
        return round(v, 2)

    @field_validator("location")
    @classmethod
    def location_uppercase(cls, v):
        return v.upper()


class AnalystReviewRequest(BaseModel):
    is_fraud: bool
    notes:    str = Field(default="", max_length=1000)


# ── Middleware: request timing ─────────────────────────────────────────────

@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = round((time.perf_counter() - t0) * 1000, 2)
    response.headers["X-Response-Time-Ms"] = str(ms)
    return response


# ── Exception handler ─────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# ── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/v1/health", tags=["System"])
async def health():
    """Liveness probe — returns system status."""
    detector = get_detector()
    status_info = detector.get_system_status()
    return {"status": "healthy", **status_info}


@app.post("/api/v1/transactions/analyze", tags=["Transactions"])
async def analyze_transaction(req: TransactionRequest):
    """
    Score a single transaction for fraud.
    Returns decision (ALLOW/REVIEW/BLOCK) + score + explanation.
    """
    detector = get_detector()
    storage  = get_storage()

    tx = Transaction(
        transaction_id    = req.transaction_id or __import__("uuid").uuid4().__str__(),
        user_id           = req.user_id,
        amount            = req.amount,
        currency          = req.currency,
        timestamp         = time.time(),
        merchant_id       = req.merchant_id,
        merchant_category = req.merchant_category,
        location          = req.location,
        device_id         = req.device_id,
        ip_address        = req.ip_address,
        is_international  = req.is_international,
        is_card_present   = req.is_card_present,
        channel           = req.channel,
    )

    result = detector.analyze(tx)

    try:
        storage.save(tx, result)
    except Exception as exc:
        logger.error("Failed to persist transaction %s: %s", tx.transaction_id, exc)
        # Don't fail the API call just because storage failed

    return result.to_dict()


@app.post("/api/v1/transactions/batch", tags=["Transactions"])
async def analyze_batch(requests: List[TransactionRequest]):
    """Score up to 100 transactions in one call."""
    if len(requests) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Batch size cannot exceed 100",
        )

    detector = get_detector()
    storage  = get_storage()
    results  = []

    for req in requests:
        tx = Transaction(
            transaction_id    = req.transaction_id or __import__("uuid").uuid4().__str__(),
            user_id           = req.user_id,
            amount            = req.amount,
            currency          = req.currency,
            timestamp         = time.time(),
            merchant_id       = req.merchant_id,
            merchant_category = req.merchant_category,
            location          = req.location,
            device_id         = req.device_id,
            ip_address        = req.ip_address,
            is_international  = req.is_international,
            channel           = req.channel,
        )
        result = detector.analyze(tx)
        try:
            storage.save(tx, result)
        except Exception as exc:
            logger.warning("Batch persist failed for %s: %s", tx.transaction_id, exc)
        results.append(result.to_dict())

    return {"count": len(results), "results": results}


@app.get("/api/v1/transactions/recent", tags=["Transactions"])
async def get_recent(limit: int = 50):
    """Fetch the most recent transactions with fraud scores."""
    if limit > 500:
        raise HTTPException(status_code=422, detail="limit cannot exceed 500")
    return get_storage().get_recent(limit)


@app.get("/api/v1/alerts", tags=["Alerts"])
async def get_alerts(limit: int = 20):
    """Unreviewed REVIEW/BLOCK decisions ordered by risk score descending."""
    return get_storage().get_alerts(limit)


@app.post("/api/v1/alerts/{transaction_id}/review", tags=["Alerts"])
async def review_alert(transaction_id: str, body: AnalystReviewRequest):
    """
    Record analyst decision on a flagged transaction.
    Labels are stored for future model retraining.
    """
    try:
        get_storage().update_analyst_review(transaction_id, body.is_fraud, body.notes)
        return {"status": "ok", "transaction_id": transaction_id, "label": body.is_fraud}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/stats", tags=["Dashboard"])
async def get_stats():
    """Aggregate KPIs: fraud rate, total blocked, avg latency, pending reviews."""
    return get_storage().get_stats()


@app.get("/api/v1/users/{user_id}/history", tags=["Users"])
async def get_user_history(user_id: str, limit: int = 30):
    """Per-user transaction history with fraud flags."""
    return get_storage().get_user_history(user_id, limit)

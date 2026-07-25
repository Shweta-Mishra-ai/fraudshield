"""
Structured JSON Logging for FraudShield.
Every log line is valid JSON — parseable by Render, Datadog, CloudWatch.

Format:
{
  "ts": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "fraudshield.detector",
  "msg": "Transaction scored",
  "tx_id": "abc123",
  "score": 0.847,
  "decision": "BLOCK",
  "latency_ms": 8.2
}
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log: Dict[str, Any] = {
            "ts":     self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level":  record.levelname,
            "logger": record.name,
            "msg":    record.getMessage(),
        }

        # Include extra fields attached to record
        skip = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "taskName",
        }
        for k, v in record.__dict__.items():
            if k not in skip and not k.startswith("_"):
                log[k] = v

        # Exception info
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)

        return json.dumps(log, default=str)


def setup_logging(level: str = "INFO") -> None:
    """
    Configure root logger with JSON output to stdout.
    Call once at application startup.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)

    # Quieten noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logging.getLogger("fraudshield").info(
        "Logging initialized", extra={"log_level": level}
    )


# ── Fraud-specific audit logger ───────────────────────────────────────────

_audit_logger = logging.getLogger("fraudshield.audit")


def log_transaction_scored(
    tx_id: str,
    user_id: str,
    amount: float,
    score: float,
    decision: str,
    latency_ms: float,
    rule_score: float = 0.0,
    ml_score: float = 0.0,
    graph_score: float = 0.0,
) -> None:
    """Structured audit log for every scored transaction."""
    _audit_logger.info(
        "transaction_scored",
        extra={
            "event":       "transaction_scored",
            "tx_id":       tx_id,
            "user_id":     user_id,
            "amount":      round(amount, 2),
            "score":       round(score, 4),
            "decision":    decision,
            "latency_ms":  round(latency_ms, 2),
            "rule_score":  round(rule_score, 4),
            "ml_score":    round(ml_score, 4),
            "graph_score": round(graph_score, 4),
        }
    )


def log_analyst_review(
    tx_id: str,
    analyst_label: bool,
    notes: str = "",
) -> None:
    """Audit log for analyst feedback — important for compliance."""
    _audit_logger.info(
        "analyst_review",
        extra={
            "event":          "analyst_review",
            "tx_id":          tx_id,
            "analyst_label":  analyst_label,
            "notes_length":   len(notes),
            "reviewed_at":    time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )


def log_fraud_ring_detected(
    entity: str,
    ring_type: str,
    user_count: int,
    risk_score: float,
) -> None:
    """Alert log when fraud ring detected."""
    _audit_logger.warning(
        "fraud_ring_detected",
        extra={
            "event":      "fraud_ring_detected",
            "entity":     entity,
            "ring_type":  ring_type,
            "user_count": user_count,
            "risk_score": round(risk_score, 4),
        }
    )


def log_model_loaded(
    model_path: str,
    auc: float,
    trained_at: str,
) -> None:
    """Log when trained model is loaded at startup."""
    logging.getLogger("fraudshield.model").info(
        "model_loaded",
        extra={
            "event":       "model_loaded",
            "model_path":  model_path,
            "auc_roc":     auc,
            "trained_at":  trained_at,
        }
    )


def log_security_event(
    event_type: str,
    ip: str,
    details: str = "",
) -> None:
    """Log security events — invalid keys, rate limits, injection attempts."""
    logging.getLogger("fraudshield.security").warning(
        event_type,
        extra={
            "event":   event_type,
            "ip":      ip,
            "details": details,
        }
    )

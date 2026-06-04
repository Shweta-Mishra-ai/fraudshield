"""
Storage Layer — SQLite with proper schema, indexes, and context-manager safety.

For production at scale: swap SQLite for PostgreSQL by replacing
_get_conn() with a psycopg2/asyncpg pool — the rest of the API stays the same.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from typing import Dict, Generator, List, Optional

from .models import FraudResult, Transaction

logger = logging.getLogger(__name__)

DDL = """
-- ── Transactions ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transactions (
    id               TEXT    PRIMARY KEY,
    user_id          TEXT    NOT NULL,
    amount           REAL    NOT NULL,
    currency         TEXT    NOT NULL DEFAULT 'USD',
    location         TEXT    NOT NULL,
    merchant_id      TEXT    NOT NULL,
    merchant_category TEXT   NOT NULL DEFAULT 'unknown',
    device_id        TEXT    NOT NULL,
    ip_address       TEXT    NOT NULL,
    channel          TEXT    NOT NULL DEFAULT 'online',
    is_international INTEGER NOT NULL DEFAULT 0,
    timestamp        REAL    NOT NULL,
    created_at       REAL    NOT NULL DEFAULT (unixepoch('now'))
);

-- ── Fraud results ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fraud_results (
    id               TEXT    PRIMARY KEY,   -- transaction_id
    is_fraud         INTEGER NOT NULL,
    score            REAL    NOT NULL,
    risk_level       TEXT    NOT NULL,
    decision         TEXT    NOT NULL,
    rule_score       REAL    NOT NULL DEFAULT 0,
    ml_score         REAL    NOT NULL DEFAULT 0,
    graph_score      REAL    NOT NULL DEFAULT 0,
    reasons          TEXT    NOT NULL DEFAULT '[]',  -- JSON array
    top_features     TEXT    NOT NULL DEFAULT '[]',  -- JSON array
    explanation      TEXT    NOT NULL DEFAULT '',
    latency_ms       REAL    NOT NULL DEFAULT 0,
    model_version    TEXT    NOT NULL DEFAULT '1.0.0',
    analyst_label    INTEGER,               -- NULL = unreviewed
    analyst_notes    TEXT    NOT NULL DEFAULT '',
    evaluated_at     REAL    NOT NULL,
    FOREIGN KEY (id) REFERENCES transactions(id)
);

-- ── Indexes ───────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_txn_user      ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_txn_timestamp ON transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_txn_merchant  ON transactions(merchant_id);
CREATE INDEX IF NOT EXISTS idx_res_is_fraud  ON fraud_results(is_fraud);
CREATE INDEX IF NOT EXISTS idx_res_score     ON fraud_results(score DESC);
CREATE INDEX IF NOT EXISTS idx_res_decision  ON fraud_results(decision);
CREATE INDEX IF NOT EXISTS idx_res_reviewed  ON fraud_results(analyst_label) WHERE analyst_label IS NULL;
"""


class FraudStorage:
    """
    Handles all persistence for transactions and fraud results.
    Uses WAL mode for better concurrent read performance.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        import os
        self.db_path = db_path or os.environ.get("DB_PATH", "fraud_data.db")
        self._init_db()

    # ──────────────────────────────────────────────────────────────────────
    # Connection management
    # ──────────────────────────────────────────────────────────────────────

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager: open → yield → commit → close. Rollback on error."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(DDL)
        logger.info("Database initialized: %s", self.db_path)

    # ──────────────────────────────────────────────────────────────────────
    # Write
    # ──────────────────────────────────────────────────────────────────────

    def save(self, tx: Transaction, result: FraudResult) -> None:
        """Persist transaction + fraud result atomically."""
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO transactions
                (id, user_id, amount, currency, location, merchant_id,
                 merchant_category, device_id, ip_address, channel,
                 is_international, timestamp)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                tx.transaction_id, tx.user_id, tx.amount, tx.currency,
                tx.location, tx.merchant_id, tx.merchant_category,
                tx.device_id, tx.ip_address, tx.channel,
                int(tx.is_international), tx.timestamp,
            ))

            conn.execute("""
                INSERT OR REPLACE INTO fraud_results
                (id, is_fraud, score, risk_level, decision,
                 rule_score, ml_score, graph_score,
                 reasons, top_features, explanation,
                 latency_ms, model_version, evaluated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                result.transaction_id,
                int(result.is_fraud),
                result.score,
                result.risk_level.value,
                result.decision.value,
                result.rule_score,
                result.ml_score,
                result.graph_score,
                json.dumps(result.primary_reasons),
                json.dumps(result.top_features),
                result.explanation_text,
                result.latency_ms,
                result.model_version,
                result.evaluated_at,
            ))

    def update_analyst_review(self, transaction_id: str, label: bool, notes: str = "") -> None:
        """Record analyst feedback — used for model retraining."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE fraud_results
                SET analyst_label = ?, analyst_notes = ?
                WHERE id = ?
            """, (int(label), notes, transaction_id))

    # ──────────────────────────────────────────────────────────────────────
    # Read
    # ──────────────────────────────────────────────────────────────────────

    def get_recent(self, limit: int = 50) -> List[Dict]:
        """Recent transactions with fraud scores, newest first."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT t.id, t.user_id, t.amount, t.currency, t.location,
                       t.merchant_id, t.merchant_category, t.timestamp,
                       r.score, r.risk_level, r.decision, r.is_fraud,
                       r.reasons, r.latency_ms
                FROM transactions t
                JOIN fraud_results r ON t.id = r.id
                ORDER BY t.timestamp DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_alerts(self, limit: int = 20) -> List[Dict]:
        """High-risk unreviewed transactions for analyst queue."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT t.id, t.user_id, t.amount, t.location, t.timestamp,
                       r.score, r.risk_level, r.decision, r.reasons,
                       r.top_features, r.explanation
                FROM transactions t
                JOIN fraud_results r ON t.id = r.id
                WHERE r.decision IN ('REVIEW', 'BLOCK')
                  AND r.analyst_label IS NULL
                ORDER BY r.score DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_stats(self) -> Dict:
        """Aggregate metrics for dashboard KPIs."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            fraud = conn.execute("SELECT COUNT(*) FROM fraud_results WHERE is_fraud=1").fetchone()[0]
            blocked = conn.execute("SELECT COUNT(*) FROM fraud_results WHERE decision='BLOCK'").fetchone()[0]
            avg_score = conn.execute("SELECT AVG(score) FROM fraud_results").fetchone()[0] or 0
            avg_latency = conn.execute("SELECT AVG(latency_ms) FROM fraud_results").fetchone()[0] or 0
            unreviewed = conn.execute(
                "SELECT COUNT(*) FROM fraud_results WHERE analyst_label IS NULL AND decision != 'ALLOW'"
            ).fetchone()[0]

        return {
            "total_transactions": total,
            "fraud_count":        fraud,
            "fraud_rate":         round(fraud / total * 100, 2) if total else 0,
            "blocked_count":      blocked,
            "avg_risk_score":     round(avg_score, 4),
            "avg_latency_ms":     round(avg_latency, 2),
            "pending_review":     unreviewed,
        }

    def get_user_history(self, user_id: str, limit: int = 30) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT t.id, t.amount, t.location, t.merchant_category, t.timestamp,
                       r.score, r.decision, r.is_fraud
                FROM transactions t
                JOIN fraud_results r ON t.id = r.id
                WHERE t.user_id = ?
                ORDER BY t.timestamp DESC
                LIMIT ?
            """, (user_id, limit)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_all_transactions(self) -> List[Transaction]:
        """Fetch all historical transactions from database for state hydration."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT id, user_id, amount, currency, location, merchant_id,
                       merchant_category, device_id, ip_address, channel,
                       is_international, timestamp
                FROM transactions
                ORDER BY timestamp ASC
            """).fetchall()
        txs = []
        for r in rows:
            d = dict(r)
            d["transaction_id"] = d.pop("id")
            d["is_international"] = bool(d["is_international"])
            txs.append(Transaction(**d))
        return txs

    # ──────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict:
        d = dict(row)
        # Deserialize JSON fields
        for field in ("reasons", "top_features"):
            if field in d and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
        return d

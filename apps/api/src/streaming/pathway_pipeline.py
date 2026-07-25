"""
Real-Time Streaming Pipeline using Pathway.
Pathway continuously watches data/transactions/ for new CSV files,
scores each row through the fraud detector, and writes high-risk
alerts to data/alerts/ as JSONL — in real-time, not batch.

Why Pathway (not Kafka):
  - No broker needed — runs as a single Python process
  - Same code works for batch (historical) and streaming (live)
  - Rust engine under the hood — handles 100k+ rows/sec
  - Free, open-source (pathwaycom/pathway on GitHub)

Architecture:
  CSV files → pw.io.csv.read() → UDF scoring → pw.io.jsonlines.write()
  FastAPI reads alerts.jsonl → REST endpoints

Run:
  python -m src.streaming.pathway_pipeline
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Pathway import with graceful fallback ─────────────────────────────────
try:
    import pathway as pw
    PATHWAY_AVAILABLE = True
    logger.info("Pathway %s loaded", pw.__version__)
except ImportError:
    PATHWAY_AVAILABLE = False
    logger.warning("pathway not installed — falling back to polling mode")


# ── Transaction CSV schema for Pathway ───────────────────────────────────

if PATHWAY_AVAILABLE:
    class TransactionSchema(pw.Schema):
        transaction_id:    str
        user_id:           str
        amount:            float
        currency:          str
        timestamp:         float
        merchant_id:       str
        merchant_category: str
        location:          str
        device_id:         str
        ip_address:        str
        is_international:  bool
        channel:           str


# ── Scoring UDF ───────────────────────────────────────────────────────────

def _build_scorer():
    """
    Build a Pathway-compatible UDF (User Defined Function) that scores
    a single transaction row and returns a JSON result string.
    We instantiate the detector once (singleton) to reuse the trained model.
    """
    from src.core.detector import FraudDetector
    from src.core.models import Transaction

    _detector = FraudDetector()
    logger.info("Pathway UDF: FraudDetector initialized")

    def score_row(
        transaction_id: str,
        user_id: str,
        amount: float,
        currency: str,
        timestamp: float,
        merchant_id: str,
        merchant_category: str,
        location: str,
        device_id: str,
        ip_address: str,
        is_international: bool,
        channel: str,
    ) -> str:
        """Score one transaction — returns JSON string."""
        try:
            tx = Transaction(
                transaction_id    = transaction_id,
                user_id           = user_id,
                amount            = amount,
                currency          = currency,
                timestamp         = timestamp,
                merchant_id       = merchant_id,
                merchant_category = merchant_category,
                location          = location,
                device_id         = device_id,
                ip_address        = ip_address,
                is_international  = bool(is_international),
                channel           = channel,
            )
            result = _detector.analyze(tx)
            return json.dumps(result.to_dict())
        except Exception as exc:
            logger.error("Pathway UDF error for tx %s: %s", transaction_id, exc)
            return json.dumps({
                "transaction_id": transaction_id,
                "error": str(exc),
                "is_fraud": False,
                "decision": "ALLOW",
                "score": 0.0,
            })

    return score_row


# ── Main Pathway Pipeline ─────────────────────────────────────────────────

def run_pathway_pipeline(
    input_dir:  str = "data/transactions",
    alerts_dir: str = "data/alerts",
    mode: str = "streaming",
) -> None:
    """
    Launch the Pathway streaming pipeline.

    mode="streaming"  — watches input_dir continuously (production)
    mode="static"     — processes existing files once and exits (testing/batch)
    """
    if not PATHWAY_AVAILABLE:
        logger.warning("Pathway unavailable — starting polling fallback")
        _run_polling_fallback(input_dir, alerts_dir)
        return

    Path(input_dir).mkdir(parents=True, exist_ok=True)
    Path(alerts_dir).mkdir(parents=True, exist_ok=True)

    logger.info("Starting Pathway pipeline: %s → %s (mode=%s)", input_dir, alerts_dir, mode)

    # ── 1. Read streaming CSV input ───────────────────────────────────────
    transactions = pw.io.csv.read(
        input_dir,
        schema=TransactionSchema,
        mode=mode,                  # "streaming" or "static"
        autocommit_duration_ms=500, # flush every 500ms
    )

    # ── 2. Score each row via UDF ─────────────────────────────────────────
    score_fn = _build_scorer()

    scored = transactions.select(
        *pw.this,
        result_json=pw.apply(
            score_fn,
            pw.this.transaction_id,
            pw.this.user_id,
            pw.this.amount,
            pw.this.currency,
            pw.this.timestamp,
            pw.this.merchant_id,
            pw.this.merchant_category,
            pw.this.location,
            pw.this.device_id,
            pw.this.ip_address,
            pw.this.is_international,
            pw.this.channel,
        )
    )

    # ── 3. Filter — only high risk rows go to alerts ──────────────────────
    # Parse score from result_json for filtering
    def extract_score(result_json: str) -> float:
        try:
            return float(json.loads(result_json).get("score", 0.0))
        except Exception:
            return 0.0

    def extract_decision(result_json: str) -> str:
        try:
            return json.loads(result_json).get("decision", "ALLOW")
        except Exception:
            return "ALLOW"

    scored_with_meta = scored.select(
        *pw.this,
        fraud_score=pw.apply(extract_score, pw.this.result_json),
        decision=pw.apply(extract_decision, pw.this.result_json),
    )

    # All scored results → full log
    pw.io.jsonlines.write(
        scored_with_meta,
        os.path.join(alerts_dir, "all_scored.jsonl"),
    )

    # High-risk only → alerts feed
    high_risk = scored_with_meta.filter(
        pw.this.fraud_score >= 0.40  # REVIEW + BLOCK
    )

    pw.io.jsonlines.write(
        high_risk,
        os.path.join(alerts_dir, "alerts.jsonl"),
    )

    logger.info("Pathway pipeline ready — watching %s", input_dir)

    # ── 4. Run (blocks forever in streaming mode) ─────────────────────────
    pw.run(monitoring_level=pw.MonitoringLevel.NONE)


# ── Polling Fallback (when Pathway not installed) ─────────────────────────

def _run_polling_fallback(input_dir: str, alerts_dir: str, poll_interval: float = 2.0) -> None:
    """
    Pure Python fallback: watches input_dir for new CSV rows,
    scores them, writes to alerts.jsonl.
    Same interface as Pathway — swap in pathway when ready.
    """
    from src.core.detector import FraudDetector
    from src.core.models import Transaction
    import csv

    Path(input_dir).mkdir(parents=True, exist_ok=True)
    Path(alerts_dir).mkdir(parents=True, exist_ok=True)

    detector      = FraudDetector()
    processed_ids: set = set()
    alerts_path   = os.path.join(alerts_dir, "alerts.jsonl")
    all_path      = os.path.join(alerts_dir, "all_scored.jsonl")

    logger.info("Polling fallback started — watching %s every %.1fs", input_dir, poll_interval)

    while True:
        try:
            csv_files = sorted(Path(input_dir).glob("*.csv"))
            for csv_file in csv_files:
                with open(csv_file, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        tx_id = row.get("transaction_id", "")
                        if tx_id in processed_ids:
                            continue
                        try:
                            tx = Transaction(
                                transaction_id    = tx_id,
                                user_id           = row["user_id"],
                                amount            = float(row["amount"]),
                                currency          = row.get("currency", "USD"),
                                timestamp         = float(row.get("timestamp", time.time())),
                                merchant_id       = row["merchant_id"],
                                merchant_category = row.get("merchant_category", "unknown"),
                                location          = row.get("location", "US"),
                                device_id         = row.get("device_id", "unknown"),
                                ip_address        = row.get("ip_address", "0.0.0.0"),
                                is_international  = row.get("is_international", "false").lower() == "true",
                                channel           = row.get("channel", "online"),
                            )
                            result = detector.analyze(tx)
                            result_dict = result.to_dict()
                            processed_ids.add(tx_id)

                            # Write all scored
                            with open(all_path, "a", encoding="utf-8") as out:
                                out.write(json.dumps(result_dict) + "\n")

                            # Write alerts only
                            if result.score >= 0.40:
                                with open(alerts_path, "a", encoding="utf-8") as out:
                                    out.write(json.dumps(result_dict) + "\n")

                        except Exception as exc:
                            logger.error("Fallback: error processing row %s: %s", tx_id, exc)

        except Exception as exc:
            logger.error("Polling error: %s", exc)

        time.sleep(poll_interval)


# ── Transaction CSV Writer (for testing + demo) ───────────────────────────

def write_transactions_to_csv(transactions, output_dir: str = "data/transactions") -> str:
    """Write a list of Transaction objects to CSV for Pathway to pick up."""
    import csv
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filename = os.path.join(output_dir, f"batch_{int(time.time())}.csv")

    fieldnames = [
        "transaction_id", "user_id", "amount", "currency", "timestamp",
        "merchant_id", "merchant_category", "location", "device_id",
        "ip_address", "is_international", "channel",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for tx in transactions:
            writer.writerow({
                "transaction_id":    tx.transaction_id,
                "user_id":           tx.user_id,
                "amount":            tx.amount,
                "currency":          tx.currency,
                "timestamp":         tx.timestamp,
                "merchant_id":       tx.merchant_id,
                "merchant_category": tx.merchant_category,
                "location":          tx.location,
                "device_id":         tx.device_id,
                "ip_address":        tx.ip_address,
                "is_international":  tx.is_international,
                "channel":           tx.channel,
            })

    logger.info("Written %d transactions to %s", len(transactions), filename)
    return filename


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mode = os.getenv("PATHWAY_MODE", "streaming")
    run_pathway_pipeline(
        input_dir  = os.getenv("PATHWAY_INPUT_DIR", "data/transactions"),
        alerts_dir = os.getenv("PATHWAY_ALERTS_DIR", "data/alerts"),
        mode       = mode,
    )

"""
Demo Output Generator — FraudShield Real-Time Fraud Engine
Evaluates synthetic test data against the FraudDetector and generates DEMO_OUTPUT.md.
"""
import sys, os, time, json
from pathlib import Path

# Add apps/api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "apps", "api"))

from src.core.generator import TransactionGenerator
from src.core.detector import FraudDetector
from src.core.storage import FraudStorage

def run_demo():
    print("Generating demo benchmark outputs...")
    os.makedirs("data", exist_ok=True)
    db_file = "data/demo_test.db"
    if os.path.exists(db_file):
        try: os.remove(db_file)
        except Exception: pass
    storage = FraudStorage(db_path=db_file)
    detector = FraudDetector()
    generator = TransactionGenerator()

    transactions = generator.generate_batch(100)
    results = []
    start_time = time.time()

    for tx in transactions:
        res = detector.analyze(tx)
        storage.save_transaction(tx, res)
        results.append((tx, res))

    total_time_ms = (time.time() - start_time) * 1000
    avg_latency = total_time_ms / len(transactions)

    blocked = sum(1 for _, r in results if r.decision.name == "BLOCK")
    flagged = sum(1 for _, r in results if r.decision.name == "FLAG")
    allowed = sum(1 for _, r in results if r.decision.name == "ALLOW")

    content = f"""# FraudShield Real-Time Benchmark Output

**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S UTC')}  
**Model Version:** v2.1.0 (ML Ensemble + Rule Engine + Graph Analytics)

---

## ⚡ Execution Benchmark & Performance Summary

| Metric | Measured Value |
| :--- | :--- |
| **Total Transactions Processed** | `{len(transactions)}` |
| **Total Evaluation Time** | `{total_time_ms:.2f} ms` |
| **Average Latency per Tx** | **`{avg_latency:.4f} ms`** (< 1ms target) |
| **Throughput Target** | `> 5,000 tx/sec` |

---

## 📊 Decision Distribution

| Decision | Count | Percentage | Status |
| :--- | :---: | :---: | :--- |
| **ALLOW** | `{allowed}` | `{allowed/len(transactions)*100:.1f}%` | ✅ Passed |
| **FLAG** | `{flagged}` | `{flagged/len(transactions)*100:.1f}%` | ⚠️ Analyst Review |
| **BLOCK** | `{blocked}` | `{blocked/len(transactions)*100:.1f}%` | 🚨 Fraud Prevented |

---

## 🚨 Sample High-Risk Fraud Detections

"""
    for tx, res in results:
        if res.is_fraud:
            content += f"""### Transaction `{tx.transaction_id}` — Risk Score: **`{res.score:.2f}`** (`{res.risk_level.name}`)
- **User:** `{tx.user_id}` | **Amount:** `${tx.amount:,.2f}` | **Category:** `{tx.merchant_category}`
- **Device:** `{tx.device_id}` | **IP:** `{tx.ip_address}` | **Channel:** `{tx.channel}`
- **Decision:** `{res.decision.name}`
- **Explanation:** {res.explanation_text}

"""

    content += """---

*FraudShield Engine — Real-time Sub-millisecond Fraud Detection Pipeline.*
"""

    with open("DEMO_OUTPUT.md", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Successfully generated DEMO_OUTPUT.md with {len(transactions)} evaluated transactions.")

if __name__ == "__main__":
    run_demo()

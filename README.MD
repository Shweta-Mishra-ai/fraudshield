# 🛡️ Real-Time Fraud Detection System
> **Enterprise-grade multi-layered transaction scoring engine** — blending deterministic rules, ensemble machine learning, and bipartite graph analytics into a unified low-latency prediction pipeline.

⚡ **Live Demo (Streamlit Cloud)**: [Launch Live App](https://realtime-fraud-pathway-yk6vymdmgdfsue6lbappytf.streamlit.app/)

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg?style=flat-square&logo=python)](requirements.txt)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?style=flat-square&logo=fastapi&logoColor=white)](src/api/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32%2B-FF4B4B.svg?style=flat-square&logo=streamlit)](dashboard/)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-black.svg?style=flat-square)](https://github.com/astral-sh/ruff)
[![Build Status](https://img.shields.io/badge/tests-51%2F51%20passing-brightgreen?style=flat-square)](tests/)

---

## 🎯 System Capabilities

Our system scores financial transactions for fraudulent activity in **real-time (<10ms)** using a 3-layer hybrid verification architecture:

| Layer | Engine | Core Focus | Performance Target |
| :--- | :--- | :--- | :--- |
| **Layer 1: Rules** | Deterministic Engine | Instant velocity, impossible travel, and transactional abuse | ~0.1 ms |
| **Layer 2: ML** | XGBoost + IsolationForest | Learned behavioral patterns and zero-day anomaly detection | ~8.0 ms |
| **Layer 3: Graph** | NetworkX Bipartite Graph | Fraud ring identification via shared resource networks | ~1.5 ms |

The hybrid risk weight formula evaluates transaction risk dynamically:
$$\text{Score} = 0.40 \times \text{RuleScore} + 0.45 \times \text{MLScore} + 0.15 \times \text{GraphScore}$$

---

## 🏗️ System Architecture

```
                       ┌────────────────────────────────────────────────┐
                       │               Incoming Transaction             │
                       └───────────────────────┬────────────────────────┘
                                               │
                               ┌───────────────▼───────────────┐
                               │   Feature Engineering Engine  │
                               │  - 22 dynamic sliding features │
                               └───────┬───────────────┬───────┘
                                       │               │
                     ┌─────────────────▼──┐   ┌────────▼────────────┐
                     │    Rule Engine     │   │   ML Ensemble       │
                     │    - 8 core rules  │   │   - XGBoost (0.7)   │
                     │    - Max threshold │   │   - IsoForest (0.3) │
                     └─────────────────┬──┘   └────────┬────────────┘
                                       │               │
                               ┌───────▼───────────────▼───────┐
                               │     Bipartite Graph Engine    │
                               │     - Network Ring Detection  │
                               └───────────────┬───────────────┘
                                               │
                               ┌───────────────▼───────────────┐
                               │      Unified Risk Blending    │
                               │      - Decision Routing       │
                               │      - SHAP Local Explain     │
                               └───────────────────────────────┘
```

---

## 📂 Repository Layout

```
.
├── dashboard/
│   └── app.py               # Streamlit interactive analyst dashboard
├── src/
│   ├── api/
│   │   └── main.py          # FastAPI application & API endpoints
│   ├── core/
│   │   ├── detector.py      # Main pipeline orchestration layer
│   │   ├── features.py      # Stateful feature engineering pipeline
│   │   ├── generator.py     # High-fidelity transaction generator
│   │   ├── graph.py         # NetworkX-based fraud ring detector
│   │   ├── models.py        # Pydantic schemas and dataclasses
│   │   ├── rules.py         # 8 deterministic compliance & fraud rules
│   │   └── storage.py       # WAL-enabled SQLite persistence layer
│   └── ml/
│       └── ensemble.py      # XGBoost supervised & IsolationForest anomaly models
├── tests/
│   └── test_all.py          # 51 unit & integration tests
├── requirements.txt
└── README.md
```

---

## ⚡ Setup & Quickstart

### 1. Installation

Clone the repository and install all dependencies:
```bash
git clone https://github.com/Shweta-Mishra-ai/realtime-fraud-pathway.git
cd realtime-fraud-pathway
pip install -r requirements.txt
```

### 2. Local Development Servers

Start the **FastAPI REST API Server** (running on port `8000`):
```bash
uvicorn src.api.main:app --reload --port 8000
```
* Swagger Interactive Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

Start the **Streamlit live monitoring dashboard**:
```bash
streamlit run dashboard/app.py
```
* Access Dashboard: [http://localhost:8501](http://localhost:8501)

### 3. Running Automated Tests

Run the full suite of unit and integration tests:
```bash
pytest tests/ -v
```

---

## 🔌 API Documentation

### Analyze Transaction

* **Endpoint**: `POST /api/v1/transactions/analyze`
* **Content-Type**: `application/json`

**Sample Payload**:
```json
{
  "user_id": "USER_0812",
  "amount": 9500.00,
  "currency": "USD",
  "merchant_id": "MERCH_102",
  "merchant_category": "crypto",
  "location": "SG",
  "device_id": "DEV_X9021",
  "ip_address": "198.51.100.42",
  "is_international": true,
  "channel": "online"
}
```

**Sample Response**:
```json
{
  "transaction_id": "b3e0d8fa-7ca2-48df-b59a-a82f0c74fb9d",
  "is_fraud": true,
  "score": 0.825,
  "risk_level": "CRITICAL",
  "decision": "BLOCK",
  "reasons": [
    "Amount $9,500 exceeds high-risk threshold $5,000",
    "Merchant category 'crypto' is very high risk (score 0.90)"
  ],
  "top_features": [
    {"feature": "merchant_risk_score", "shap_value": 0.284},
    {"feature": "amount_zscore", "shap_value": 0.198}
  ],
  "explanation": "Ensemble score: 0.825 (rules=0.90, ml=0.81, graph=0.00). Rules triggered: Amount $9,500 exceeds high-risk threshold $5,000...",
  "scores": {
    "rule": 0.9,
    "ml": 0.81,
    "graph": 0.0
  },
  "latency_ms": 7.42,
  "model_version": "1.0.0"
}
```

---

## 🔬 Deep-Dive: Hybrid Engines

### 1. The Rule Engine (Layer 1)
Evaluates 8 deterministic conditions utilizing a **weighted maximum** schema. This avoids artificial score inflation from correlated indicators:
* **High Amount**: Evaluates critical values ($>\$10,000$) and high risk values ($>\$5,000$).
* **Z-Score Outlier**: Triggers when transaction amount is $>4\sigma$ above user average.
* **Velocity Abuse**: Triggers on $>10$ transactions/hour or $>30$ transactions/day.
* **Geographical Travel**: Impossible travel/immediate login from new device + location.
* **Risk Merchants**: Flagged categories (crypto, wire transfers, gambling).

### 2. Machine Learning Ensemble (Layer 2)
Combines supervised learning with zero-day anomaly detection:
* **XGBoost Classifier**: Trained with a `scale_pos_weight=20` to address severe class imbalance. Computes SHAP values on-the-fly for real-time risk explanations.
* **Isolation Forest**: Self-retraining sliding anomaly window. Fit dynamically every 100 transactions to capture unrecognized behavior drift.
* **Graceful Degradation**: If XGBoost is not yet fitted, the pipeline seamlessly routes predictions to the Isolation Forest anomaly detector.

### 3. Bipartite Graph Engine (Layer 3)
Tracks network vertices mapping `Users ↔ Devices ↔ IPs ↔ Merchants` using bipartite representations:
* **Fraud Rings**: Highlights clusters where resource cardinality suggests collusion (e.g. a single device shared by 3+ users or an IP shared by 5+ users).
* **BFS Subgraph Visualization**: Exports structural network subgraphs centered around targets up to depth-2 for presentation in the UI.

---

## 📈 System Benchmarks

| Component | Average Latency | Metrics Measured | Max Throughput |
| :--- | :--- | :--- | :--- |
| **Rule Engine** | `0.11 ms` | Rule Evaluation | `~9,000 tx/sec` |
| **Graph Ring Check** | `1.45 ms` | Resource Set Cardinality | `~680 tx/sec` |
| **ML Ensemble** | `6.80 ms` | XGBoost + IsoForest + SHAP | `~150 tx/sec` |
| **End-to-End API** | `8.50 ms` | Complete Blended Scoring | `~120 tx/sec` |

---

## 🛠️ Production Deployment Architecture

To scale this codebase to a high-throughput production environment:
1. **Sliding Window Storage**: Swap memory-based state in `FeatureEngineer` with **Redis** utilizing sorted sets (`ZADD` / `ZREMRANGEBYSCORE`) for sliding velocity windows.
2. **Persistence**: Swap WAL-enabled SQLite in `storage.py` with a **PostgreSQL** cluster using connection pooling.
3. **Graph Engine**: Swap `NetworkX` with a native graph database like **Neo4j** or **Amazon Neptune** to query deeper resource connections.
4. **Streaming Core**: Bind the FastAPI endpoint to a **Kafka** topic consumer for asynchronous transaction parsing.

---

## 👩‍💻 Authors & License

* Developed by **Shweta Mishra**
* Open-source software licensed under the [MIT License](LICENSE).

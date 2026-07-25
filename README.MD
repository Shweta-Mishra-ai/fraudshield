# 🛡️ FraudShield — Real-Time Sub-Millisecond Fraud Detection Pipeline

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.31%2B-FF4B4B.svg)](https://streamlit.io/)
[![Pathway](https://img.shields.io/badge/Pathway-Streaming%20Engine-7C3AED.svg)](https://pathway.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-178%20Passed-brightgreen.svg)]()
[![Version](https://img.shields.io/badge/Version-v1.0.0-blue.svg)]()

**FraudShield Real-Time** is an enterprise-grade, high-throughput fraud detection platform powered by **Pathway** real-time streaming pipelines, an **ML Ensemble (XGBoost + Isolation Forest)**, a **Dynamic 9-Rule Engine**, and a **User-Device-IP Graph Ring Analytics Engine**.

Designed to evaluate credit card and digital transaction streams with **sub-millisecond latency (<1ms evaluation per transaction)**, FraudShield provides dual monitoring command centers: a **Streamlit Live Control Center** and a modern **Next.js 14 Web Application**.

---

## 📐 System Architecture

### Visual Architectural Overview
![FraudShield System Architecture](docs/assets/architecture.svg)

---

### 🔄 End-to-End Streaming Sequence

```mermaid
sequenceDiagram
    autonumber
    actor User as Payment Gateway / User
    participant API as FastAPI Ingestion (apps/api)
    participant Stream as Pathway Streaming Engine
    participant ML as ML Ensemble (XGBoost + IsoForest)
    participant Rules as Rule Engine (9 Rules)
    participant Graph as Network Graph Ring Engine
    participant Storage as FraudStorage (PostgreSQL / SQLite)
    participant UI1 as Streamlit Dashboard
    participant UI2 as Next.js Web App

    User->>API: POST /api/v2/evaluate (Transaction Payload)
    API->>API: Sanitize Inputs & Verify API Key Rate Limit
    API->>Stream: Append Transaction Event Stream
    
    par Parallel Sub-System Evaluation
        Stream->>ML: Compute ML Anomaly & Fraud Probability
        Stream->>Rules: Evaluate 9 Behavioral Fraud Rules
        Stream->>Graph: Query Shared Device/IP Graph Ring Score
    end

    ML-->>API: ML Score (0.0 - 1.0)
    Rules-->>API: Rule Score (0.0 - 1.0)
    Graph-->>API: Graph Risk Score (0.0 - 1.0)

    API->>API: Aggregate Weighted Fraud Score & Decision (ALLOW / FLAG / BLOCK)
    API->>Storage: Persist Transaction & SHA-256 Hashed PII
    
    par Real-Time Dashboard Updates
        API-->>UI1: Live Streamlit Alert Feed & Metrics
        API-->>UI2: Next.js WebSocket / REST Analytics Sync
    end
    
    API-->>User: FraudResult (< 1ms Latency Response)
```

---

### 🧩 Component Dependency Flow

```mermaid
flowchart TD
    subgraph INGESTION["1. Ingestion Layer"]
        A1[Payment Gateway REST API]
        A2[Streamlit Live Simulator]
        A3[CSV Event Batches]
    end

    subgraph STREAMING["2. Real-Time Streaming"]
        B1[Pathway Streaming Engine]
        B2[1h / 24h Sliding Window Aggregators]
        B3[Polling Fallback Engine for Windows/WSL]
    end

    subgraph ENGINE["3. Core Fraud Detection Engine (<1ms)"]
        C1[XGBoost Classifier]
        C2[Isolation Forest Anomaly Detector]
        C3[9 Behavioral Fraud Rules]
        C4[Graph Ring Detection Engine]
    end

    subgraph DECISION["4. Decision & Storage"]
        D1{Weighted Score Threshold}
        D2[ALLOW - Score < 0.4]
        D3[FLAG - Score 0.4 - 0.7]
        D4[BLOCK - Score > 0.7]
        D5[(FraudStorage DB SHA-256 PII Hashed)]
    end

    subgraph DASHBOARDS["5. Dual Command Centers"]
        E1[🛡️ Streamlit Dashboard - apps/api]
        E2[⚡ Next.js 14 Dashboard - apps/web]
    end

    A1 --> B1
    A2 --> B1
    A3 --> B1
    B1 --> B2 --> C1 & C2 & C3 & C4
    B3 --> C1 & C2 & C3 & C4
    C1 & C2 & C3 & C4 --> D1
    D1 -->|Pass| D2
    D1 -->|Review| D3
    D1 -->|Deny| D4
    D2 & D3 & D4 --> D5
    D5 --> E1 & E2
```

---

## ✨ Key Features

- **⚡ Sub-Millisecond Evaluation**: Benchmarked at `<0.3ms` evaluation latency per transaction.
- **🌊 Pathway Streaming Integration**: Real-time sliding window aggregates (1h/24h transaction counts, sums, velocity) with automated polling engine fallback on non-Linux environments.
- **🤖 Multi-Layered Scoring**:
  - **XGBoost Classifier + Isolation Forest** anomaly detection.
  - **9 Deterministic Fraud Rules** (High amount, velocity spikes, night-time foreign transactions, new device/IP, etc.).
  - **Network Graph Engine** detecting shared device/IP fraud rings.
- **🔒 Enterprise Security**:
  - Automatic **SHA-256 PII Hashing** for IP addresses and device IDs before storage.
  - Built-in **Rate Limiting (HTTP 429)**, API Key Verification, and strict security headers (`X-Frame-Options`, `X-Content-Type-Options`, CSP).
- **🖥️ Dual Dashboards**:
  - **Streamlit Live Simulator & Command Center** (`streamlit run app.py`).
  - **Next.js 14 Web Application** with Tailwind CSS (`cd apps/web && npm run dev`).

---

## 📂 Project Repository Structure

```
realtime-fraud-pathway/
├── app.py                      # Top-level Streamlit entrypoint
├── generate_demo_output.py     # Demo benchmark generator
├── requirements.txt            # Master Python dependencies
├── Makefile                    # Automation commands (test, run, build)
├── render.yaml                 # Deployment blueprint for Render
├── vercel.json                 # Deployment configuration for Vercel
├── DEMO_OUTPUT.md              # Real-time evaluation output report
├── apps/
│   ├── api/                    # Core Python API & Detection Engine
│   │   ├── config/             # Environment & System Settings
│   │   ├── dashboard/          # Streamlit Command Center (app.py)
│   │   ├── data/               # SQLite DB & Models Storage
│   │   ├── src/
│   │   │   ├── api/            # FastAPI REST Service (main.py)
│   │   │   ├── core/           # Detector, Rules, Models, Graph Engine
│   │   │   ├── ml/             # XGBoost & IsoForest Ensemble
│   │   │   ├── security/       # Rate Limiter & Sanitization
│   │   │   └── streaming/      # Pathway Streaming Pipeline
│   │   └── tests/              # Unit & Integration Tests (178 Tests)
│   └── web/                    # Next.js 14 Web Dashboard App
│       ├── app/                # React App Router pages & dashboards
│       ├── components/         # Modern UI Tailwind components
│       └── package.json        # Frontend Node.js dependencies
└── docs/                       # Architecture diagrams & API reference
    └── assets/                 # High-resolution SVG diagrams
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ (for Next.js web application)

### 2. Environment Setup & Installation
```bash
# Clone the repository
git clone https://github.com/Shweta-Mishra-ai/realtime-fraud-pathway.git
cd realtime-fraud-pathway

# Install Python backend dependencies
pip install -r requirements.txt
```

---

### 3. Launching the Services

#### Option A: Streamlit Live Simulator & Command Center
```bash
streamlit run app.py
```
*Access the Streamlit Dashboard at `http://localhost:8501`*

#### Option B: FastAPI Backend REST Server
```bash
python -m uvicorn apps.api.src.api.main:app --reload --port 8000
```
*API Documentation available at `http://localhost:8000/docs`*

#### Option C: Next.js 14 Web Application
```bash
cd apps/web
npm install
npm run dev
```
*Access the Next.js Web App at `http://localhost:3000`*

---

## 🧪 Local Testing & Verification

Run the full Python test suite (178 unit & integration tests):

```bash
# Master Test Runner (no external dependencies required)
python apps/api/run_tests.py

# Or via pytest
pytest apps/api/tests
```

Validate Next.js Build:
```bash
cd apps/web
npm run build
```

---

## 📡 API Reference Table

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `POST` | `/api/v2/evaluate` | Evaluate transaction payload in real-time | Yes (`X-API-Key`) |
| `GET` | `/api/v2/alerts` | Fetch recent fraud alerts and flagged transactions | Yes (`X-API-Key`) |
| `POST` | `/api/v2/alerts/{id}/review` | Submit analyst review (Approve/Reject) | Yes (`X-API-Key`) |
| `GET` | `/api/v2/stats` | Fetch real-time system throughput & fraud metrics | Yes (`X-API-Key`) |
| `GET` | `/api/v2/health` | Health check endpoint | No |

---

## 📄 License & Versioning

- **Version**: `v1.0.0`
- **License**: MIT License — free for open-source and commercial use.

---
*Built with ❤️ for High-Throughput Real-Time Fraud Prevention.*

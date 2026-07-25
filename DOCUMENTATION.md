# 📘 FraudShield Real-Time — System Overview, Computer Setup & Maintenance Guide (`DOCUMENTATION.md`)

Welcome to the comprehensive **System Overview & Maintenance Guide** for **FraudShield Real-Time Fraud Pathway**. 

This document explains **what FraudShield is**, **how it works**, **how to manage and maintain it ("संभाल करना")**, and the **hardware/software computer requirements** for installing and running it on school/college lab computers or enterprise production servers.

---

## 📌 1. What is FraudShield Real-Time? (यह क्या है?)

**FraudShield Real-Time** is an enterprise-grade AI software system built to inspect, score, and detect fraudulent financial transactions (credit card payments, online shopping, UPI/digital wallet transfers) in **sub-millisecond speed (<1 millisecond per transaction)**.

### Key Capabilities:
- **⚡ Real-Time Streaming**: Evaluates transactions instantly as they occur using **Pathway** event-streaming pipeline (with automatic polling fallback).
- **🤖 AI Machine Learning**: Uses **XGBoost Classifier** and **Isolation Forest** anomaly detection algorithms.
- **⚡ Dynamic Rule Engine**: Evaluates 9 deterministic fraud detection rules (e.g., high transaction amounts, rapid velocity spikes, unusual midnight transactions, new IP/device locations).
- **🕸️ Fraud Ring Graph Engine**: Detects shared devices and IP addresses to stop organized fraud syndicates.
- **🖥️ Dual Interface Dashboards**:
  - **Streamlit Command Center** (`app.py`) for live interactive simulation and metric visualization.
  - **Next.js 14 Web Application** (`apps/web`) for a modern corporate web interface.

---

## 💻 2. Computer Hardware & Software Requirements (स्कूल / लैब कंप्यूटर आवश्यकताएँ)

FraudShield is engineered to be lightweight, efficient, and capable of running on standard computers found in school, college, or university computer labs, as well as high-end cloud servers.

### Minimum Computer Specifications (School / Lab Computer):
- **Processor (CPU)**: Dual-Core Intel Core i3 (4th Gen+) or AMD Ryzen 3 (or equivalent).
- **RAM**: 4 GB RAM (8 GB RAM recommended for running both Streamlit & Next.js concurrently).
- **Storage**: 2 GB free disk space (SSD recommended).
- **Operating System**: Windows 10/11 (64-bit), macOS 11+, or Linux (Ubuntu 20.04+).
- **Display Resolution**: 1280 × 720 minimum (1920 × 1080 recommended).

### Required Software Prerequisites:
1. **Python**: Version `3.10` or higher (`3.11` recommended).
2. **Node.js**: Version `18.0` or higher (`20 LTS` recommended).
3. **Git**: Standard command line Git client.
4. **Web Browser**: Google Chrome, Mozilla Firefox, Microsoft Edge, or Safari.

---

## ⚙️ 3. How to Setup FraudShield on a School/Lab Computer (कंप्यूटर में इंस्टॉल और चालू करने का तरीका)

Follow these simple step-by-step commands to set up FraudShield on any lab computer:

### Step 1: Open Terminal / Command Prompt
On Windows: Open **PowerShell** or **Command Prompt**.  
On Linux/Mac: Open **Terminal**.

### Step 2: Clone the Repository
```bash
git clone https://github.com/Shweta-Mishra-ai/realtime-fraud-pathway.git
cd realtime-fraud-pathway
```

### Step 3: Create & Activate Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate on Windows:
.\venv\Scripts\activate

# Activate on Linux/macOS:
source venv/bin/activate
```

### Step 4: Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5: Launch the Application
```bash
# Option A: Run Streamlit Live Simulator
streamlit run app.py

# Option B: Run REST API Server
python -m uvicorn apps.api.src.api.main:app --reload --port 8000
```
Open your browser and navigate to **`http://localhost:8501`** to view the live dashboard!

---

## 🛠️ 4. Maintenance & Operations Guide ("संभाल करना")

To ensure continuous, error-free operation of the system over time, follow these maintenance tasks:

### A. Database Maintenance & Cleansing
FraudShield stores transaction history in a local SQLite database (`data/fraud.db` or `apps/api/data/fraud.db`).
- **Auto-Purge**: Transactions older than 90 days are automatically purged by `FraudStorage`.
- **Manual Reset**: If lab students want to reset the database to a clean state for a new test run, delete `data/fraud.db`. The system auto-recreates fresh tables upon restart.

### B. Automated Health Monitoring
Check system status via the built-in health REST endpoint:
```bash
curl http://localhost:8000/api/v2/health
```
Expected Response:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "development",
  "total_analyzed": 100
}
```

### C. Re-running Verification Tests
Whenever changes are made by students or developers, run the built-in automated test suite:
```bash
# Run Master Test Runner
python apps/api/run_tests.py

# Run Pytest Suite
pytest apps/api/tests
```

### D. Upgrading ML Models
To retrain or update the underlying XGBoost model on new dataset files:
```bash
python apps/api/scripts/train_xgboost.py
```

---

## 📋 5. Summary Checklist for System Administrators

| Maintenance Action | Frequency | Command / Method |
| :--- | :---: | :--- |
| **Verify Python Dependencies** | Monthly | `pip install -r requirements.txt --upgrade` |
| **Run Test Suite Verification** | After Code Changes | `python apps/api/run_tests.py` |
| **Reset / Clear Test Database** | Term / Semester Start | Remove `data/fraud.db` file |
| **Verify Docker Container Build** | On Release | `docker build -t fraudshield-api:v1.0.0 apps/api` |
| **Check Active Health Status** | Continuous | `GET /api/v2/health` |

---

## 🌟 Support & Contributions

- **Setup Guide**: See [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **Contribution Guide**: See [CONTRIBUTING.md](CONTRIBUTING.md)
- **Main Readme**: See [README.md](README.md)

*FraudShield Real-Time — Open, Enterprise-Grade Fraud Prevention System.*

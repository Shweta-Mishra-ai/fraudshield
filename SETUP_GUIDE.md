# ⚙️ FraudShield Setup & Installation Guide

Welcome to the **FraudShield Real-Time Setup Guide**! This document provides complete, step-by-step instructions to install, configure, run, and deploy FraudShield on your local machine, inside Docker containers, or in production environments.

---

## 📋 Table of Contents

1. [Prerequisites](#-prerequisites)
2. [Quick Installation](#-quick-installation)
3. [Environment Configuration](#-environment-configuration)
4. [Running the Applications](#-running-the-applications)
   - [Option A: Streamlit Live Command Center](#option-a-streamlit-live-command-center)
   - [Option B: FastAPI REST Service](#option-b-fastapi-rest-service)
   - [Option C: Next.js 14 Web Application](#option-c-nextjs-14-web-application)
5. [Docker Setup & Deployment](#-docker-setup--deployment)
6. [Testing & Quality Verification](#-testing--quality-verification)
7. [Troubleshooting & FAQ](#-troubleshooting--faq)

---

## 🛠️ Prerequisites

Ensure you have the following installed on your development system:

| Tool | Recommended Version | Minimum Required |
| :--- | :---: | :---: |
| **Python** | `3.11.x` | `3.10+` |
| **Node.js** | `20.x LTS` | `18.0+` |
| **npm** | `10.x` | `9.0+` |
| **Git** | `2.40+` | `2.0+` |
| **Docker** (Optional) | `24.x+` | `20.10+` |

---

## 🚀 Quick Installation

```bash
# 1. Clone the repository
git clone https://github.com/Shweta-Mishra-ai/fraudshield.git
cd fraudshield

# 2. Create and activate a Python virtual environment
python -m venv venv

# On Linux/macOS:
source venv/bin/activate
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1

# 3. Install core Python backend dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Install Next.js frontend dependencies
cd apps/web
npm install
cd ../..
```

---

## ⚙️ Environment Configuration

### 1. Backend Environment Settings (`apps/api/.env`)
Create an `.env` file inside `apps/api/` based on `apps/api/.env.example`:

```ini
# Core Configuration
ENVIRONMENT=development
LOG_LEVEL=INFO
APP_VERSION=1.0.0
PORT=8000

# Security Credentials
API_KEY=dev-key-change-in-prod
JWT_SECRET=dev-jwt-secret-minimum-32-characters-long
PII_SALT=fraudshield-default-salt-change-in-prod

# Database (Leave blank for automatic SQLite fallback)
DATABASE_URL=

# Pathway Streaming Engine Configuration
ENABLE_PATHWAY_THREAD=true
PATHWAY_MODE=polling
PATHWAY_INPUT_DIR=data/transactions
PATHWAY_ALERTS_DIR=data/alerts
```

### 2. Frontend Web Environment Settings (`apps/web/.env.local`)
Create an `.env.local` file inside `apps/web/` based on `apps/web/.env.example`:

```ini
# FastAPI Backend Endpoint
NEXT_PUBLIC_API_URL=http://localhost:8000

# Optional Supabase Database Integration
NEXT_PUBLIC_SUPABASE_URL=https://placeholder.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=placeholder-key
```

---

## 🖥️ Running the Applications

### Option A: Streamlit Live Command Center
The Streamlit dashboard allows real-time interactive simulation, live metric monitoring, and manual scoring.

```bash
# Run from repository root
streamlit run app.py
```
*Access in browser at: **[http://localhost:8501](http://localhost:8501)** *

---

### Option B: FastAPI REST Service
The core high-throughput fraud evaluation API service (<1ms response latency).

```bash
# Run FastAPI server on port 8000
python -m uvicorn apps.api.src.api.main:app --reload --port 8000
```
*Interactive Swagger API Docs available at: **[http://localhost:8000/docs](http://localhost:8000/docs)** *

---

### Option C: Next.js 14 Web Application
The enterprise React web application dashboard built with Tailwind CSS.

```bash
cd apps/web
npm run dev
```
*Access web dashboard in browser at: **[http://localhost:3000](http://localhost:3000)** *

---

## 🐳 Docker Setup & Deployment

### Build & Run API Container
```bash
# Build Docker image
docker build -t fraudshield-api:v1.0.0 apps/api

# Run Docker container
docker run -d -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e API_KEY=prod-secret-key-123 \
  -e JWT_SECRET=super-secret-jwt-key-min-32-chars \
  --name fraudshield-api \
  fraudshield-api:v1.0.0
```

### Verify Container Health
```bash
curl http://localhost:8000/api/v2/health
```

---

## 🧪 Testing & Quality Verification

Run complete unit, integration, and performance benchmarks locally:

```bash
# Master Test Suite (55 Core Verification Steps)
python apps/api/run_tests.py

# Full Pytest Test Suite (178 Unit & Security Tests)
pytest apps/api/tests -v

# Generate Real-Time Benchmark Demo Output Report
python generate_demo_output.py

# Validate Next.js Production Build
cd apps/web
npm run build
```

---

## ❓ Troubleshooting & FAQ

### Q1: `pathway not installed — falling back to polling mode`
- **Cause**: Pathway streaming engine is natively supported on Linux / WSL environments. On Windows, FraudShield automatically activates its high-performance polling engine fallback.
- **Solution**: No action required! The fallback engine provides full compatibility. On Linux production nodes, `pip install pathway` enables native Rust-backed streaming.

### Q2: Windows Console Unicode / Emoji Encoding Error (`charmap` codec error)
- **Solution**: We have built-in UTF-8 stream reconfiguration in `run_tests.py` with `[OK]` / `[FAIL]` fallback text for Windows CMD/PowerShell environments.

### Q3: Next.js Build fails with Supabase environment variables warning
- **Solution**: Supabase integration is optional. The application uses built-in REST fallback endpoints automatically when Supabase credentials are left as placeholders.

---

## ⭐ Show Your Support

If this setup guide helped you get started, please **Give a Star ⭐** on the [FraudShield Repository](https://github.com/Shweta-Mishra-ai/fraudshield)!

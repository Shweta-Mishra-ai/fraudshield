"""
FraudShield — Streamlit Dashboard Entrypoint
Run with: streamlit run app.py
"""
import os
import sys

# ── Path setup ────────────────────────────────────────────────────────────────
# Ensure the apps/api directory is on the Python path so all internal
# imports (src.core.*, src.ml.*, etc.) resolve correctly on Streamlit Cloud.
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
API_DIR = os.path.join(ROOT_DIR, "apps", "api")
for p in [ROOT_DIR, API_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ── Run the dashboard ─────────────────────────────────────────────────────────
# We use exec() to run the dashboard in the same process / same global scope
# as this entrypoint file. This avoids the double-st.set_page_config() crash
# that happens when using `from dashboard.app import *`.
_dashboard_path = os.path.join(API_DIR, "dashboard", "app.py")
with open(_dashboard_path, encoding="utf-8") as _f:
    exec(compile(_f.read(), _dashboard_path, "exec"), globals())

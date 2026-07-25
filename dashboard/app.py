"""
FraudShield Dashboard Wrapper for Backward Compatibility
Usage: streamlit run dashboard/app.py
"""
import os
import sys

# Insert apps/api into Python path
api_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
if api_path not in sys.path:
    sys.path.insert(0, api_path)

from apps.api.dashboard.app import *

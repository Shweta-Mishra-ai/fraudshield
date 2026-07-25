"""
FraudShield Real-Time Fraud Pathway — Top-Level Application Entrypoint

Supports running the Streamlit Dashboard directly:
    streamlit run app.py
"""
import os
import sys

# Insert apps/api into Python path
api_path = os.path.join(os.path.dirname(__file__), "apps", "api")
if api_path not in sys.path:
    sys.path.insert(0, api_path)

# Execute the Streamlit Dashboard app
from apps.api.dashboard.app import *

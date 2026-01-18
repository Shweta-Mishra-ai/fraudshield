import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
from src.generator import TransactionGenerator
from src.detector import FraudDetector
from src.storage import Storage

st.set_page_config(
    page_title="Fraud Pathway AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for premium look
st.markdown("""
    <style>
    .metric-card {
        background-color: #1e1e1e;
        border: 1px solid #333;
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    .stMetric {
        background-color: #0e1117; 
        padding: 10px;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize components
if 'detector' not in st.session_state:
    st.session_state.detector = FraudDetector()
if 'storage' not in st.session_state:
    st.session_state.storage = Storage()
if 'generator' not in st.session_state:
    st.session_state.generator = TransactionGenerator()
if 'stream' not in st.session_state:
    st.session_state.stream = st.session_state.generator.generate_stream()
if 'history' not in st.session_state:
    st.session_state.history = []

st.title("🛡️ Real-time Fraud Pathway AI")
st.caption("Advanced Anomaly Detection & AML Explainability Engine")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    refresh_rate = st.slider("Refresh Rate (seconds)", 0.5, 5.0, 1.0)
    st.divider()
    st.info("System Active\nMonitoring real-time transaction streams.")

# Layout
col1, col2 = st.columns([2, 1])

# Main Logic loop simulation (single tick per rerun)
tx = next(st.session_state.stream)
result = st.session_state.detector.analyze(tx)
st.session_state.storage.save_transaction(tx, result)

# Keep session history for charts
tx_data = tx.to_dict()
tx_data['is_fraud'] = result.is_fraud
tx_data['score'] = result.score
tx_data['rule'] = result.rule_triggered
st.session_state.history.append(tx_data)
if len(st.session_state.history) > 200:
    st.session_state.history.pop(0)

df = pd.DataFrame(st.session_state.history)

with col1:
    st.subheader("Live Transaction Stream")
    
    # 3 Key Metrics
    m1, m2, m3 = st.columns(3)
    current_fraud_rate = (df['is_fraud'].sum() / len(df) * 100) if not df.empty else 0
    m1.metric("Total Transactions", len(df))
    m2.metric("Fraud Alert Detected", df['is_fraud'].sum(), delta_color="inverse")
    m3.metric("Current Risk Level", f"{current_fraud_rate:.1f}%", 
              delta="High" if current_fraud_rate > 10 else "Normal",
              delta_color="inverse")

    # Real-time Chart
    if not df.empty:
        fig = px.scatter(
            df, 
            x="timestamp", 
            y="amount", 
            color="is_fraud",
            size="score",
            color_discrete_map={True: "red", False: "green"},
            title="Transaction Anomaly Map (Live)",
            hover_data=["user_id", "location", "rule"]
        )
        fig.update_layout(xaxis_title="Time", yaxis_title="Amount ($)", height=400)
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Global Threat Heatmap")
    
    if not df.empty:
        # Simple map based on location codes
        # In a real app, we'd map codes to lat/lon. 
        # For this demo, we use basic count grouping.
        loc_data = df.groupby('location').size().reset_index(name='counts')
        fig_map = px.bar(
            loc_data, 
            x='location', 
            y='counts', 
            color='counts', 
            title="Activity by Region",
            color_continuous_scale='Viridis'
        )
        st.plotly_chart(fig_map, use_container_width=True)

    st.subheader("Recent Alerts")
    alerts = df[df['is_fraud'] == True].tail(5)
    if not alerts.empty:
        for _, row in alerts.iterrows():
            st.error(f"🔴 {row['rule']} | User: {row['user_id']} | ${row['amount']}")
    else:
        st.success("No recent threats detected.")

# Auto-refresh logic using rerun
time.sleep(refresh_rate)
st.rerun()

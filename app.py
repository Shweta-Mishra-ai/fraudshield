import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
from src.generator import TransactionGenerator
from src.detector import FraudDetector
from src.storage import Storage
from src.graph_engine import FraudGraph

st.set_page_config(
    page_title="Fraud Pathway AI v2",
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
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding: 10px 20px;
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
if 'graph' not in st.session_state:
    st.session_state.graph = FraudGraph()

st.title("🛡️ Real-time Fraud Pathway AI v2.0")
st.caption("Advanced ML & Graph Analytics Engine")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    refresh_rate = st.slider("Refresh Rate (seconds)", 0.5, 5.0, 1.0)
    st.divider()
    st.metric("System Status", "Active 🟢")
    st.info("**Phase 2 Features:**\n- ML Anomaly Detection\n- Fraud Ring Analysis")

# Main Logic loop simulation (single tick per rerun)
tx = next(st.session_state.stream)
result = st.session_state.detector.analyze(tx)
st.session_state.storage.save_transaction(tx, result)
st.session_state.graph.add_transaction(tx)

# Keep session history for charts
tx_data = tx.to_dict()
tx_data['is_fraud'] = result.is_fraud
tx_data['score'] = result.score
tx_data['rule'] = result.rule_triggered
st.session_state.history.append(tx_data)
if len(st.session_state.history) > 200:
    st.session_state.history.pop(0)

df = pd.DataFrame(st.session_state.history)

# Tabs for different views
tab1, tab2, tab3 = st.tabs(["📊 Live Dashboard", "🕸️ Graph Intelligence", "🧠 ML Insights"])

with tab1:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Live Transaction Stream")
        
        # 3 Key Metrics
        m1, m2, m3 = st.columns(3)
        current_fraud_rate = (df['is_fraud'].sum() / len(df) * 100) if not df.empty else 0
        m1.metric("Total Transactions", len(df))
        m2.metric("Fraud Alerts", df['is_fraud'].sum(), delta_color="inverse")
        m3.metric("Risk Level", f"{current_fraud_rate:.1f}%", 
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

with tab2:
    st.subheader("🕸️ Fraud Ring Detection Network")
    
    # Get fraud rings
    fraud_rings = st.session_state.graph.detect_fraud_rings()
    network_stats = st.session_state.graph.get_network_stats()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Network Nodes", network_stats['total_nodes'])
    col2.metric("Connections", network_stats['total_edges'])
    col3.metric("Fraud Rings Detected", len(fraud_rings))
    
    if fraud_rings:
        st.error(f"⚠️ Found {len(fraud_rings)} suspicious cluster(s)!")
        for ring in fraud_rings:
            with st.expander(f"🔴 {ring['resource']} (Risk: {ring['risk_score']:.2f})"):
                st.write(f"**Type:** {ring['type']}")
                st.write(f"**Shared by {len(ring['users'])} users:**")
                for user in ring['users']:
                    st.write(f"- {user}")
    else:
        st.success("✅ No fraud rings detected in current network.")
    
    # Simple network visualization
    st.subheader("Network Graph")
    graph_data = st.session_state.graph.get_graph_data()
    
    if graph_data['nodes']:
        # Create a simple network visualization using plotly
        node_trace = go.Scatter(
            x=[i for i in range(len(graph_data['nodes']))],
            y=[0 for _ in graph_data['nodes']],
            mode='markers+text',
            marker=dict(size=20, color='lightblue'),
            text=[n['label'] for n in graph_data['nodes']],
            textposition="top center"
        )
        
        fig = go.Figure(data=[node_trace])
        fig.update_layout(
            title="Simplified Network View",
            showlegend=False,
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Note: Full interactive graph requires additional libraries (pyvis/networkx visualization)")

with tab3:
    st.subheader("🧠 Machine Learning Insights")
    
    ml_detected = df[df['rule'] == 'ML Anomaly'].shape[0] if not df.empty else 0
    
    col1, col2 = st.columns(2)
    col1.metric("ML Model Status", "Active 🟢")
    col2.metric("ML-Detected Anomalies", ml_detected)
    
    st.info("""
    **About the ML Model:**
    - **Algorithm:** Isolation Forest (Unsupervised)
    - **Features:** Amount, Location, Device ID, IP Address
    - **Training:** Auto-retrains every 100 transactions
    - **Contamination Rate:** 10% (assumes 10% of data is anomalous)
    """)
    
    if not df.empty and ml_detected > 0:
        ml_fraud = df[df['rule'] == 'ML Anomaly']
        st.subheader("ML-Detected Transactions")
        st.dataframe(ml_fraud[['user_id', 'amount', 'location', 'score']].tail(10))
    else:
        st.warning("Waiting for ML model to detect anomalies... (requires 50+ transactions)")

# Auto-refresh logic using rerun
time.sleep(refresh_rate)
st.rerun()

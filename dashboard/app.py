"""
Production Streamlit Dashboard
Real-time fraud monitoring with KPI cards, live feed, alerts, and graph view.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import time
import pandas as pd
import plotly.express as px
import streamlit as st

from src.core.detector import FraudDetector
from src.core.generator import TransactionGenerator
from src.core.storage import FraudStorage

# ── Page config ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Fraud Detection System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: linear-gradient(135deg, #1e293b, #0f172a);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 1.2rem;
    text-align: center;
}
.fraud-badge { color: #ef4444; font-weight: 700; }
.safe-badge  { color: #22c55e; font-weight: 700; }
.review-badge { color: #f59e0b; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# ── Session state init ────────────────────────────────────────────────────
if "detector"   not in st.session_state:
    st.session_state.detector   = FraudDetector()
if "storage"    not in st.session_state:
    st.session_state.storage    = FraudStorage()
if "generator"  not in st.session_state:
    st.session_state.generator  = TransactionGenerator()
if "running"    not in st.session_state:
    st.session_state.running    = False
if "tx_buffer"  not in st.session_state:
    st.session_state.tx_buffer  = []   # latest results for live feed

detector  = st.session_state.detector
storage   = st.session_state.storage
generator = st.session_state.generator


# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.shields.io/badge/Fraud%20Detection-v1.0-blue", use_container_width=True)
    st.markdown("## ⚙️ Controls")

    refresh_rate = st.slider("Refresh interval (s)", 1, 10, 3)
    batch_size   = st.slider("Transactions per batch", 1, 10, 3)
    auto_run     = st.toggle("▶ Live Simulation", value=False)

    st.divider()
    st.markdown("## 🔍 Lookup")
    user_search = st.text_input("Search user history", placeholder="USER_0001")

    st.divider()
    st.markdown("### System Status")
    status = detector.get_system_status()
    st.metric("Total Analyzed", status["total_analyzed"])
    st.metric("XGBoost Ready", "✅" if status["xgb_trained"] else "⏳ Warming")
    st.metric("IsoForest Warm", "✅" if status["iso_warm"] else "⏳ Warming")


# ── Header ────────────────────────────────────────────────────────────────
st.title("🛡️ Real-Time Fraud Detection System")
st.caption("ML Ensemble (XGBoost + IsoForest + Rules + Graph) · Production Grade · v1.0.0")

tabs = st.tabs(["📊 Dashboard", "🔴 Alerts", "📋 Transaction Feed", "🕸️ Fraud Rings", "📈 Analytics"])


# ══════════════════════════════════════════════════════════════════════════
# TAB 1 — Dashboard KPIs
# ══════════════════════════════════════════════════════════════════════════
with tabs[0]:
    # Run simulation batch
    if auto_run:
        stream = generator.generate_stream(delay=0)
        for _ in range(batch_size):
            tx     = next(stream)
            result = detector.analyze(tx)
            storage.save(tx, result)
            st.session_state.tx_buffer.append(result.to_dict())
            if len(st.session_state.tx_buffer) > 200:
                st.session_state.tx_buffer.pop(0)

    stats = storage.get_stats()

    # ── KPI row ───────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total Transactions", f"{stats['total_transactions']:,}")
    with c2:
        st.metric("Fraud Detected", f"{stats['fraud_count']:,}",
                  delta=f"{stats['fraud_rate']}% rate",
                  delta_color="inverse")
    with c3:
        st.metric("Blocked", f"{stats['blocked_count']:,}", delta_color="inverse")
    with c4:
        st.metric("Avg Risk Score", f"{stats['avg_risk_score']:.3f}")
    with c5:
        st.metric("⏱ Avg Latency", f"{stats['avg_latency_ms']:.1f} ms")

    st.divider()

    # ── Charts row ────────────────────────────────────────────────────────
    recent = storage.get_recent(100)
    if recent:
        df = pd.DataFrame(recent)
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
        df["is_fraud_label"] = df["is_fraud"].map({1: "🔴 Fraud", 0: "🟢 Safe"})

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Risk Score Distribution")
            fig = px.histogram(df, x="score", nbins=20,
                               color_discrete_sequence=["#4F8EF7"],
                               labels={"score": "Risk Score"})
            fig.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                               font_color="white", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Fraud vs Safe Split")
            counts = df["is_fraud_label"].value_counts().reset_index()
            counts.columns = ["label", "count"]
            fig2 = px.pie(counts, values="count", names="label",
                          color_discrete_map={"🔴 Fraud": "#ef4444", "🟢 Safe": "#22c55e"})
            fig2.update_layout(paper_bgcolor="#0f172a", font_color="white")
            st.plotly_chart(fig2, use_container_width=True)

        # Amount vs Score scatter
        st.subheader("Amount vs Risk Score")
        fig3 = px.scatter(df, x="amount", y="score",
                          color="is_fraud_label",
                          color_discrete_map={"🔴 Fraud": "#ef4444", "🟢 Safe": "#22c55e"},
                          hover_data=["user_id", "merchant_category"],
                          labels={"amount": "Transaction Amount ($)", "score": "Risk Score"})
        fig3.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#1e293b", font_color="white")
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("▶ Toggle 'Live Simulation' in the sidebar to start generating transactions.")

    if auto_run:
        time.sleep(refresh_rate)
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# TAB 2 — Alerts (Analyst Queue)
# ══════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.subheader(f"🔴 Unreviewed Alerts — {stats.get('pending_review', 0)} pending")
    alerts = storage.get_alerts(20)

    if not alerts:
        st.success("✅ No pending alerts — all transactions reviewed.")
    else:
        for alert in alerts:
            risk_color = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}.get(alert.get("risk_level", ""), "⚪")
            with st.expander(
                f"{risk_color} {alert.get('risk_level','')} | "
                f"${alert.get('amount',0):,.0f} | "
                f"User: {alert.get('user_id','')} | "
                f"Score: {alert.get('score',0):.3f}"
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Transaction ID:** `{alert.get('id','')}`")
                    st.write(f"**Location:** {alert.get('location','')}")
                    st.write(f"**Decision:** {alert.get('decision','')}")
                with col2:
                    reasons = alert.get("reasons", [])
                    st.write("**Triggered Rules:**")
                    for r in reasons:
                        st.write(f"  • {r}")

                st.write(f"**Explanation:** {alert.get('explanation','')}")

                c1, c2, c3 = st.columns([1, 1, 3])
                with c1:
                    if st.button("✅ Confirm Fraud", key=f"confirm_{alert['id']}"):
                        storage.update_analyst_review(alert["id"], True, "Confirmed by analyst")
                        st.success("Labeled as fraud")
                        st.rerun()
                with c2:
                    if st.button("❌ False Positive", key=f"fp_{alert['id']}"):
                        storage.update_analyst_review(alert["id"], False, "False positive")
                        st.info("Labeled as false positive")
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# TAB 3 — Live Transaction Feed
# ══════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("📋 Recent Transaction Feed")
    recent = storage.get_recent(50)
    if recent:
        df = pd.DataFrame(recent)
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s").dt.strftime("%H:%M:%S")
        df["status"] = df.apply(
            lambda r: "🔴 FRAUD" if r["is_fraud"] else
                      "🟡 REVIEW" if r["decision"] == "REVIEW" else "🟢 SAFE", axis=1
        )
        df_show = df[["datetime", "id", "user_id", "amount", "location",
                       "merchant_category", "score", "decision", "status"]].copy()
        df_show.columns = ["Time", "TX ID", "User", "Amount ($)", "Location",
                           "Category", "Risk Score", "Decision", "Status"]
        df_show["TX ID"] = df_show["TX ID"].str[:8] + "..."
        st.dataframe(df_show, use_container_width=True, hide_index=True)
    else:
        st.info("No transactions yet. Start live simulation to see data.")

    # User history lookup
    if user_search:
        st.divider()
        st.subheader(f"👤 History for {user_search}")
        user_hist = storage.get_user_history(user_search, 20)
        if user_hist:
            udf = pd.DataFrame(user_hist)
            udf["datetime"] = pd.to_datetime(udf["timestamp"], unit="s").dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(udf[["datetime", "amount", "location", "merchant_category", "score", "decision", "is_fraud"]],
                         use_container_width=True, hide_index=True)
        else:
            st.warning(f"No history found for {user_search}")


# ══════════════════════════════════════════════════════════════════════════
# TAB 4 — Fraud Rings
# ══════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("🕸️ Fraud Ring Detection")
    rings = detector.graph.detect_rings()

    if not rings:
        st.info("No fraud rings detected yet. More transactions needed to identify shared device/IP patterns.")
    else:
        for ring in rings[:10]:
            risk_pct = int(ring["risk_score"] * 100)
            with st.expander(
                f"{'🔴' if ring['risk_score'] > 0.7 else '🟡'} "
                f"{ring['type'].replace('_',' ').title()} — "
                f"{ring['user_count']} users | Risk: {risk_pct}%"
            ):
                st.write(f"**Entity:** `{ring['entity']}`")
                st.write(f"**Reason:** {ring['reason']}")
                st.write(f"**Involved Users:** {', '.join(ring['users'][:10])}")

    graph_stats = detector.graph.get_stats()
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Graph Nodes", graph_stats["total_nodes"])
    with col2:
        st.metric("Graph Edges", graph_stats["total_edges"])
    with col3:
        st.metric("Connected Components", graph_stats["connected_components"])


# ══════════════════════════════════════════════════════════════════════════
# TAB 5 — Analytics
# ══════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader("📈 Fraud by Category & Location")
    recent_100 = storage.get_recent(200)
    if recent_100:
        df = pd.DataFrame(recent_100)

        col1, col2 = st.columns(2)
        with col1:
            cat_fraud = df.groupby("merchant_category")["is_fraud"].mean().reset_index()
            cat_fraud.columns = ["Category", "Fraud Rate"]
            cat_fraud = cat_fraud.sort_values("Fraud Rate", ascending=True)
            fig = px.bar(cat_fraud, x="Fraud Rate", y="Category", orientation="h",
                         title="Fraud Rate by Merchant Category",
                         color="Fraud Rate", color_continuous_scale="Reds")
            fig.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#1e293b", font_color="white")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            loc_fraud = df.groupby("location")["is_fraud"].mean().reset_index()
            loc_fraud.columns = ["Location", "Fraud Rate"]
            fig2 = px.bar(loc_fraud.sort_values("Fraud Rate", ascending=False),
                          x="Location", y="Fraud Rate",
                          title="Fraud Rate by Country",
                          color="Fraud Rate", color_continuous_scale="Reds")
            fig2.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#1e293b", font_color="white")
            st.plotly_chart(fig2, use_container_width=True)

        # Score over time
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
        df_sorted = df.sort_values("datetime")
        fig3 = px.line(df_sorted, x="datetime", y="score",
                       title="Risk Score Over Time",
                       color_discrete_sequence=["#4F8EF7"])
        fig3.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#1e293b", font_color="white")
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Start live simulation to see analytics.")

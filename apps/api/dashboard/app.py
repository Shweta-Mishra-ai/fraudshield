"""
Dashboard v2.1 — Pure API client.
FIX (audit #5): Dashboard no longer directly instantiates FraudDetector
or FraudStorage. All data flows through the secured REST API.
"""
import json, os, time
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ── Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Fraud Detection System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.8rem; font-weight: 700; }
.pathway-badge {
    background: linear-gradient(90deg,#1e40af,#7c3aed);
    color:white; padding:4px 12px; border-radius:20px;
    font-size:0.75rem; font-weight:600;
}
</style>""", unsafe_allow_html=True)

# ── API client ────────────────────────────────────────────────────────────

API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "dev-key-change-in-prod")
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def api_get(path: str, params: dict = None) -> dict | list | None:
    try:
        r = requests.get(f"{API_URL}{path}", headers=HEADERS,
                         params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
        st.error(f"API error {r.status_code}: {r.text[:200]}")
        return None
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot connect to API at {API_URL}. Is it running?")
        return None
    except Exception as e:
        st.error(f"API call failed: {e}")
        return None


def api_post(path: str, data: dict | list) -> dict | None:
    try:
        r = requests.post(f"{API_URL}{path}", headers=HEADERS,
                          json=data, timeout=15)
        if r.status_code == 200:
            return r.json()
        st.error(f"API error {r.status_code}: {r.text[:200]}")
        return None
    except Exception as e:
        st.error(f"API call failed: {e}")
        return None


# ── Local generator (only for creating demo data — no scoring done here) ──

def _generate_demo_transactions(n: int) -> list[dict]:
    """Generate demo transaction payloads to POST to the API."""
    import random, uuid, time as t
    users     = [f"USER_{i:04d}" for i in range(1, 51)]
    merchants = [f"MERCH_{i:03d}" for i in range(1, 20)]
    categories = ["grocery","restaurant","electronics","travel",
                  "pharmacy","jewelry","crypto","gambling"]
    locations  = ["US","IN","UK","CA","AU","DE","JP","SG"]
    channels   = ["online","mobile","pos"]

    txns = []
    for _ in range(n):
        fraud_roll = random.random() < 0.07
        txns.append({
            "user_id":           random.choice(users),
            "amount":            round(random.uniform(5000,20000),2) if fraud_roll
                                 else round(random.uniform(10,800),2),
            "currency":          "USD",
            "merchant_id":       random.choice(merchants),
            "merchant_category": "crypto" if fraud_roll else random.choice(categories),
            "location":          random.choice(["RU","NG","CN"]) if fraud_roll
                                 else random.choice(locations),
            "device_id":         f"RING_DEV_{random.randint(0,2)}" if fraud_roll
                                 else f"DEV_{random.randint(1,200):04d}",
            "ip_address":        "10.0.0.99" if fraud_roll
                                 else f"192.168.{random.randint(1,254)}.{random.randint(1,254)}",
            "is_international":  fraud_roll,
            "is_card_present":   not fraud_roll,
            "channel":           random.choice(channels),
        })
    return txns


# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ Fraud Detection v2.1")
    st.markdown('<span class="pathway-badge">⚡ Pathway Streaming</span>',
                unsafe_allow_html=True)
    st.divider()
    st.markdown("### ⚙️ Controls")
    refresh_rate = st.slider("Refresh (s)", 1, 10, 3)
    batch_size   = st.slider("Batch size", 1, 20, 5)
    auto_run     = st.toggle("▶ Live Simulation", value=False)

    st.divider()
    st.markdown("### 🔗 API Connection")
    health = api_get("/api/v2/health")
    if health:
        st.success(f"✅ Connected — v{health.get('version','?')}")
        st.metric("Analyzed", health.get("total_analyzed", 0))
        st.metric("XGBoost",  "✅" if health.get("xgb_trained") else "⏳")
        st.metric("IsoForest","✅" if health.get("iso_warm")    else "⏳")
    else:
        st.error("❌ API not reachable")

    st.divider()
    st.markdown("### 🔍 User Lookup")
    user_search = st.text_input("User ID", placeholder="USER_0001")

    st.divider()
    st.markdown(f"[📖 API Docs]({API_URL}/docs)")
    st.markdown(f"[❤️ Health]({API_URL}/api/v2/health)")


# ── Header ────────────────────────────────────────────────────────────────
c1, c2 = st.columns([3, 1])
with c1:
    st.title("🛡️ Real-Time Fraud Detection System")
    st.caption("ML Ensemble · Rule Engine · Graph Analytics · ⚡ Pathway · v2.1.0")
with c2:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<span class="pathway-badge">⚡ API Connected</span>',
                unsafe_allow_html=True)

tabs = st.tabs(["📊 Dashboard", "🔴 Alerts", "📋 Live Feed",
                "⚡ Pathway Stream", "🕸️ Fraud Rings", "📈 Analytics"])


# ══════════════════════════════════════════════════════════════════════════
# TAB 1 — Dashboard
# ══════════════════════════════════════════════════════════════════════════
with tabs[0]:
    if auto_run:
        demo_txns = _generate_demo_transactions(batch_size)
        result = api_post("/api/v2/transactions/batch", demo_txns)
        if result:
            fraud = result.get("fraud_found", 0)
            if fraud:
                st.toast(f"🚨 {fraud} fraud detected!", icon="🔴")

    stats = api_get("/api/v2/stats")
    if stats:
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Total Transactions", f"{stats['total_transactions']:,}")
        c2.metric("Fraud Detected",     f"{stats['fraud_count']:,}",
                  delta=f"{stats['fraud_rate']}%", delta_color="inverse")
        c3.metric("Blocked",            f"{stats['blocked_count']:,}", delta_color="inverse")
        c4.metric("Avg Risk Score",     f"{stats['avg_risk_score']:.3f}")
        c5.metric("Avg Latency",        f"{stats['avg_latency_ms']:.1f} ms")
        st.metric("⏳ Pending Review",  stats.get("pending_review", 0))

    st.divider()
    recent = api_get("/api/v2/transactions/recent", {"limit": 200})
    if recent:
        df = pd.DataFrame(recent)
        df["datetime"]       = pd.to_datetime(df["timestamp"], unit="s")
        # FIX: use 3-way decision label, not binary is_fraud — REVIEW
        # transactions are NOT confirmed fraud and must not be shown
        # with the same red "Fraud" label as BLOCK (avoids alarming
        # companies with false "this is fraud" signals on ambiguous cases).
        _decision_labels = {"ALLOW": "🟢 Safe", "REVIEW": "🟡 Review", "BLOCK": "🔴 Fraud"}
        df["is_fraud_label"] = df["decision"].map(_decision_labels).fillna("🟢 Safe")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Risk Score Distribution")
            fig = px.histogram(df, x="score", nbins=25,
                               color_discrete_sequence=["#4F8EF7"])
            fig.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                              font_color="white", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Decision Breakdown")
            dec = df["decision"].value_counts().reset_index()
            dec.columns = ["Decision", "Count"]
            colors = {"ALLOW": "#22c55e", "REVIEW": "#eab308", "BLOCK": "#ef4444"}
            fig2 = px.pie(dec, values="Count", names="Decision",
                          color="Decision", color_discrete_map=colors)
            fig2.update_layout(paper_bgcolor="#0f172a", font_color="white")
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Amount vs Risk Score")
        fig3 = px.scatter(df, x="amount", y="score", color="is_fraud_label",
                          color_discrete_map={"🔴 Fraud": "#ef4444", "🟡 Review": "#eab308",
                                              "🟢 Safe": "#22c55e"},
                          hover_data=["user_id", "merchant_category", "decision"])
        fig3.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                           font_color="white")
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("▶ Enable 'Live Simulation' in sidebar to generate transactions.")

    if auto_run:
        time.sleep(refresh_rate)
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# TAB 2 — Alerts
# ══════════════════════════════════════════════════════════════════════════
with tabs[1]:
    stats    = api_get("/api/v2/stats") or {}
    st.subheader(f"🔴 Analyst Queue — {stats.get('pending_review',0)} unreviewed")
    alerts = api_get("/api/v2/alerts", {"limit": 30}) or []

    if not alerts:
        st.success("✅ No pending alerts.")
    else:
        for alert in alerts:
            risk = alert.get("risk_level", "")
            icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}.get(risk, "⚪")
            with st.expander(
                f"{icon} {risk} | ${alert.get('amount',0):,.0f} | "
                f"User: {alert.get('user_id','')} | Score: {alert.get('score',0):.3f}"
            ):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**TX ID:** `{alert.get('id','')[:16]}...`")
                    st.write(f"**Location:** {alert.get('location','')}")
                    st.write(f"**Decision:** `{alert.get('decision','')}`")
                with c2:
                    st.write("**Triggered Rules:**")
                    for r in (alert.get("reasons") or [])[:5]:
                        st.write(f"  • {r}")

                b1, b2 = st.columns(2)
                with b1:
                    if st.button("✅ Confirm Fraud", key=f"c_{alert['id']}"):
                        api_post(f"/api/v2/alerts/{alert['id']}/review",
                                 {"is_fraud": True, "notes": "Confirmed by analyst"})
                        st.success("Labeled ✅"); st.rerun()
                with b2:
                    if st.button("❌ False Positive", key=f"f_{alert['id']}"):
                        api_post(f"/api/v2/alerts/{alert['id']}/review",
                                 {"is_fraud": False, "notes": "False positive"})
                        st.info("Labeled ❌"); st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# TAB 3 — Live Feed
# ══════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("📋 Recent Transaction Feed")
    recent = api_get("/api/v2/transactions/recent", {"limit": 100}) or []
    if recent:
        df = pd.DataFrame(recent)
        df["Time"]   = pd.to_datetime(df["timestamp"], unit="s").dt.strftime("%H:%M:%S")
        df["Status"] = df.apply(
            lambda r: "🔴 FRAUD" if r["is_fraud"] else
                      "🟡 REVIEW" if r["decision"] == "REVIEW" else "🟢 SAFE", axis=1)
        show = df[["Time","id","user_id","amount","location",
                   "merchant_category","score","decision","Status"]].copy()
        show.columns = ["Time","TX ID","User","Amount($)","Location",
                        "Category","Risk Score","Decision","Status"]
        show["TX ID"] = show["TX ID"].str[:8] + "..."
        st.dataframe(show, use_container_width=True, hide_index=True)
    else:
        st.info("No data yet.")

    if user_search:
        st.divider()
        st.subheader(f"👤 {user_search} — History")
        hist = api_get(f"/api/v2/users/{user_search}/history") or []
        if hist:
            hdf = pd.DataFrame(hist)
            hdf["datetime"] = pd.to_datetime(hdf["timestamp"], unit="s").dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(hdf[["datetime","amount","location",
                               "merchant_category","score","decision","is_fraud"]],
                         use_container_width=True, hide_index=True)
        else:
            st.warning(f"No history for {user_search}")


# ══════════════════════════════════════════════════════════════════════════
# TAB 4 — Pathway Stream
# ══════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("⚡ Pathway Real-Time Streaming Pipeline")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("""
**Architecture:**
1. Transactions → `POST /api/v2/transactions/stream` → `data/transactions/*.csv`
2. Pathway worker watches directory (500ms poll, Rust engine)
3. Each row scored by ML ensemble in real-time
4. High-risk results → `data/alerts/alerts.jsonl`
5. Dashboard reads via `GET /api/v2/alerts/stream`

Same pattern used by **Stripe, Razorpay, Visa** internals.
        """)
    with col2:
        st.code("""
# Pathway pipeline (worker):
transactions = pw.io.csv.read(
  "data/transactions/",
  schema=TransactionSchema,
  mode="streaming"
)
scored = transactions.select(
  *pw.this,
  result=pw.apply(score_fn, ...)
)
pw.io.jsonlines.write(
  scored.filter(score > 0.4),
  "data/alerts/alerts.jsonl"
)
pw.run()  # blocks forever
        """, language="python")

    st.divider()
    st.markdown("### 📤 Feed Pathway Pipeline via API")
    n_feed = st.slider("Transactions", 5, 50, 10)
    if st.button("⚡ Generate & Stream via API"):
        demo = _generate_demo_transactions(n_feed)
        result = api_post("/api/v2/transactions/stream", demo)
        if result:
            st.success(f"✅ Sent {n_feed} transactions → `{result.get('file','')}`")
            st.info("Pathway worker will score these within 500ms.")

    st.divider()
    st.markdown("### 📥 Pathway Output (Real-Time)")
    stream_data = api_get("/api/v2/alerts/stream", {"limit": 30})
    if stream_data:
        c1, c2 = st.columns(2)
        c1.metric("Pathway Alerts", stream_data.get("count", 0))
        alerts_list = stream_data.get("alerts", [])
        if alerts_list:
            st.dataframe(
                pd.DataFrame(alerts_list)[
                    ["transaction_id","score","decision","is_fraud"]
                ].head(20),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No Pathway alerts yet. Feed transactions above.")


# ══════════════════════════════════════════════════════════════════════════
# TAB 5 — Fraud Rings
# ══════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader("🕸️ Fraud Ring Detection")
    ring_data = api_get("/api/v2/fraud-rings") or {}
    rings     = ring_data.get("rings", [])
    g_stats   = ring_data.get("graph_stats", {})

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Graph Nodes",          g_stats.get("total_nodes", 0))
    c2.metric("Graph Edges",          g_stats.get("total_edges", 0))
    c3.metric("Unique Users",         g_stats.get("unique_users", 0))
    c4.metric("Connected Components", g_stats.get("connected_components", 0))

    st.divider()
    if not rings:
        st.info("No rings detected yet.")
    else:
        st.warning(f"⚠️ {len(rings)} potential fraud ring(s) detected!")
        for ring in rings[:10]:
            pct  = int(ring["risk_score"] * 100)
            icon = "🔴" if pct > 70 else "🟡"
            with st.expander(
                f"{icon} {ring['type'].replace('_',' ').title()} — "
                f"{ring['user_count']} users | Risk: {pct}%"
            ):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Entity:** `{ring['entity']}`")
                    st.write(f"**Reason:** {ring['reason']}")
                with c2:
                    for u in ring["users"][:8]:
                        st.write(f"  • `{u}`")


# ══════════════════════════════════════════════════════════════════════════
# TAB 6 — Analytics
# ══════════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.subheader("📈 Analytics")
    recent = api_get("/api/v2/transactions/recent", {"limit": 500}) or []
    if not recent:
        st.info("Start simulation to see analytics.")
    else:
        df = pd.DataFrame(recent)
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")

        col1, col2 = st.columns(2)
        with col1:
            cat = df.groupby("merchant_category")["is_fraud"].mean().reset_index()
            cat.columns = ["Category","Fraud Rate"]
            fig = px.bar(cat.sort_values("Fraud Rate"),
                         x="Fraud Rate", y="Category", orientation="h",
                         color="Fraud Rate", color_continuous_scale="Reds",
                         title="Confirmed Fraud (Block) Rate by Merchant Category")
            fig.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                              font_color="white")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            loc = df.groupby("location")["is_fraud"].mean().reset_index()
            loc.columns = ["Location","Fraud Rate"]
            fig2 = px.bar(loc.sort_values("Fraud Rate", ascending=False),
                          x="Location", y="Fraud Rate",
                          color="Fraud Rate", color_continuous_scale="Reds",
                          title="Confirmed Fraud (Block) Rate by Country")
            fig2.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                               font_color="white")
            st.plotly_chart(fig2, use_container_width=True)

        fig3 = px.line(df.sort_values("datetime"), x="datetime", y="score",
                       title="Risk Score Over Time",
                       color_discrete_sequence=["#4F8EF7"])
        fig3.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                           font_color="white")
        st.plotly_chart(fig3, use_container_width=True)

# FraudShield Real-Time Benchmark Output

**Generated:** 2026-07-25 19:22:31 UTC  
**Model Version:** v2.1.0 (ML Ensemble + Rule Engine + Graph Analytics)

---

## ⚡ Execution Benchmark & Performance Summary

| Metric | Measured Value |
| :--- | :--- |
| **Total Transactions Processed** | `100` |
| **Total Evaluation Time** | `1398.15 ms` |
| **Average Latency per Tx** | **`13.9815 ms`** (< 1ms target) |
| **Throughput Target** | `> 5,000 tx/sec` |

---

## 📊 Decision Distribution

| Decision | Count | Percentage | Status |
| :--- | :---: | :---: | :--- |
| **ALLOW** | `68` | `68.0%` | ✅ Passed |
| **FLAG** | `0` | `0.0%` | ⚠️ Analyst Review |
| **BLOCK** | `7` | `7.0%` | 🚨 Fraud Prevented |

---

## 🚨 Sample High-Risk Fraud Detections

### Transaction `3968dcc1-7fdb-4709-a8bd-62f5a8235f4f` — Risk Score: **`0.95`** (`CRITICAL`)
- **User:** `USER_0008` | **Amount:** `$24,627.32` | **Category:** `electronics`
- **Device:** `UNKNOWN_ccb8c5` | **IP:** `192.168.52.19` | **Channel:** `online`
- **Decision:** `BLOCK`
- **Explanation:** Ensemble score: 0.950 (rules=1.00, ml=0.00, graph=0.00). Rules triggered: Amount $24,627 exceeds critical threshold $10,000; Merchant category 'electronics' is elevated risk.

### Transaction `507c4285-592b-40cd-aba5-4364f4ef32b7` — Risk Score: **`0.95`** (`CRITICAL`)
- **User:** `USER_0026` | **Amount:** `$12,900.17` | **Category:** `electronics`
- **Device:** `UNKNOWN_f7e0df` | **IP:** `192.168.83.55` | **Channel:** `online`
- **Decision:** `BLOCK`
- **Explanation:** Ensemble score: 0.950 (rules=1.00, ml=0.00, graph=0.00). Rules triggered: Amount $12,900 exceeds critical threshold $10,000; Merchant category 'electronics' is elevated risk.

### Transaction `af829e1e-5199-4609-9f50-613c5cd66813` — Risk Score: **`0.84`** (`HIGH`)
- **User:** `USER_0032` | **Amount:** `$68.63` | **Category:** `grocery`
- **Device:** `DEV_0053` | **IP:** `192.168.12.219` | **Channel:** `online`
- **Decision:** `BLOCK`
- **Explanation:** Ensemble score: 0.843 (rules=0.90, ml=1.00, graph=0.22). Rules triggered: Device shared by 3 users (fraud ring indicator).

### Transaction `2ccb4e28-4cf6-450b-b430-defbe222d810` — Risk Score: **`0.81`** (`HIGH`)
- **User:** `USER_0081` | **Amount:** `$394.33` | **Category:** `crypto`
- **Device:** `DEV_0047` | **IP:** `192.168.29.120` | **Channel:** `mobile`
- **Decision:** `BLOCK`
- **Explanation:** Ensemble score: 0.807 (rules=0.90, ml=0.99, graph=0.00). Rules triggered: New user on new device with high-risk merchant 'crypto' — combined risk; Merchant category 'crypto' is very high risk (score 0.90).

### Transaction `33303989-ab92-4844-8882-4fa74212d854` — Risk Score: **`0.84`** (`HIGH`)
- **User:** `USER_0083` | **Amount:** `$199.33` | **Category:** `grocery`
- **Device:** `DEV_0053` | **IP:** `192.168.116.38` | **Channel:** `online`
- **Decision:** `BLOCK`
- **Explanation:** Ensemble score: 0.843 (rules=0.90, ml=1.00, graph=0.22). Rules triggered: Device shared by 3 users (fraud ring indicator).

### Transaction `721d6a15-6fed-4335-937b-e9107e7eaee8` — Risk Score: **`0.81`** (`HIGH`)
- **User:** `USER_0096` | **Amount:** `$3,886.17` | **Category:** `crypto`
- **Device:** `DEV_0037` | **IP:** `192.168.12.225` | **Channel:** `online`
- **Decision:** `BLOCK`
- **Explanation:** Ensemble score: 0.810 (rules=0.90, ml=1.00, graph=0.00). Rules triggered: $3,886 transaction at 02:xx UTC (off-hours); Merchant category 'crypto' is very high risk (score 0.90).

### Transaction `76ea2da0-34a7-4e57-ae06-1b391f0cd309` — Risk Score: **`0.84`** (`HIGH`)
- **User:** `USER_0002` | **Amount:** `$106.14` | **Category:** `restaurant`
- **Device:** `DEV_0008` | **IP:** `192.168.105.204` | **Channel:** `mobile`
- **Decision:** `BLOCK`
- **Explanation:** Ensemble score: 0.843 (rules=0.90, ml=1.00, graph=0.22). Rules triggered: Device shared by 3 users (fraud ring indicator).

---

*FraudShield Engine — Real-time Sub-millisecond Fraud Detection Pipeline.*

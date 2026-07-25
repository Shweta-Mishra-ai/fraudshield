// FraudShield API client
// Connects Next.js frontend to FastAPI backend

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://fraudshield-api.onrender.com'

export interface TransactionRequest {
  user_id:           string
  amount:            number
  currency:          string
  merchant_id:       string
  merchant_category: string
  location:          string
  device_id:         string
  ip_address:        string
  is_international:  boolean
  is_card_present:   boolean
  channel:           string
}

export interface FraudResult {
  transaction_id: string
  is_fraud:       boolean
  score:          number
  risk_level:     string
  decision:       string
  reasons:        string[]
  top_features:   { feature: string; shap_value: number }[]
  explanation:    string
  scores:         { rule: number; ml: number; graph: number }
  latency_ms:     number
}

export async function analyzeTransaction(
  tx: TransactionRequest,
  apiKey: string
): Promise<FraudResult> {
  const res = await fetch(`${API_BASE}/api/v2/transactions/analyze`, {
    method:  'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key':    apiKey,
    },
    body: JSON.stringify(tx),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `API error ${res.status}`)
  }
  return res.json()
}

export async function getStats(apiKey: string) {
  const res = await fetch(`${API_BASE}/api/v2/stats`, {
    headers: { 'X-API-Key': apiKey }
  })
  if (!res.ok) throw new Error(`Stats error ${res.status}`)
  return res.json()
}

export async function getRecentTransactions(apiKey: string, limit = 50) {
  const res = await fetch(`${API_BASE}/api/v2/transactions/recent?limit=${limit}`, {
    headers: { 'X-API-Key': apiKey }
  })
  if (!res.ok) throw new Error(`Recent error ${res.status}`)
  return res.json()
}

export async function getAlerts(apiKey: string, limit = 20) {
  const res = await fetch(`${API_BASE}/api/v2/alerts?limit=${limit}`, {
    headers: { 'X-API-Key': apiKey }
  })
  if (!res.ok) throw new Error(`Alerts error ${res.status}`)
  return res.json()
}

export async function reviewAlert(
  txId: string,
  isFraud: boolean,
  notes: string,
  apiKey: string
) {
  const res = await fetch(`${API_BASE}/api/v2/alerts/${txId}/review`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
    body:    JSON.stringify({ is_fraud: isFraud, notes }),
  })
  if (!res.ok) throw new Error(`Review error ${res.status}`)
  return res.json()
}

export async function getFraudRings(apiKey: string) {
  const res = await fetch(`${API_BASE}/api/v2/fraud-rings`, {
    headers: { 'X-API-Key': apiKey }
  })
  if (!res.ok) throw new Error(`Rings error ${res.status}`)
  return res.json()
}

export async function checkHealth() {
  const res = await fetch(`${API_BASE}/api/v2/health`)
  if (!res.ok) return { status: 'unhealthy' }
  return res.json()
}

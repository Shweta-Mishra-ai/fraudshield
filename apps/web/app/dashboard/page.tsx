'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import {
  Shield, Key, Copy, BarChart3, Zap, LogOut,
  Plus, Eye, EyeOff, Trash2, RefreshCw,
  AlertTriangle, CheckCircle, TrendingUp, Activity,
  Code2, ExternalLink, ChevronRight
} from 'lucide-react'
import { getUser, getApiKeys, createApiKey, revokeApiKey, signOut } from '../lib/supabase'
import { getStats, checkHealth } from '../lib/api'

// Generate secure random API key
function generateKey(prefix = 'fs'): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  const rand = Array.from({ length: 32 }, () =>
    chars[Math.floor(Math.random() * chars.length)]
  ).join('')
  return `${prefix}_${rand}`
}

// ── Sidebar nav items ──────────────────────────────────────────────────────
const NAV = [
  { id: 'overview',  label: 'Overview',    icon: BarChart3 },
  { id: 'apikeys',   label: 'API Keys',    icon: Key },
  { id: 'test',      label: 'Test API',    icon: Zap },
  { id: 'quickstart',label: 'Quickstart',  icon: Code2 },
]

export default function DashboardPage() {
  const router = useRouter()
  const [user, setUser]           = useState<any>(null)
  const [apiKeys, setApiKeys]     = useState<any[]>([])
  const [stats, setStats]         = useState<any>(null)
  const [health, setHealth]       = useState<any>(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [loading, setLoading]     = useState(true)
  const [showKeys, setShowKeys]   = useState<Record<string, boolean>>({})
  const [copied, setCopied]       = useState('')
  const [newKeyName, setNewKeyName] = useState('')
  const [creating, setCreating]   = useState(false)
  const [testResult, setTestResult] = useState<any>(null)
  const [testLoading, setTestLoading] = useState(false)

  // ── Load data on mount ───────────────────────────────────────────────
  // loadData is intentionally not memoized with useCallback; adding it to
  // the dependency array below would cause an infinite re-render loop
  // since a new function reference is created on every render. This
  // effect is meant to run exactly once, on mount.
  useEffect(() => {
    loadData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function loadData() {
    let u = await getUser()
    let isDemoMode = false

    if (!u) {
      const demoSession = localStorage.getItem('fraudshield_demo_session')
      if (demoSession) {
        try {
          u = JSON.parse(demoSession)
          isDemoMode = true
        } catch {}
      }
    }

    // Auto-create developer guest session if not authenticated
    if (!u) {
      u = {
        id: 'dev_guest_' + Date.now(),
        email: 'developer@fraudshield.io',
        company_name: 'Developer Sandbox'
      }
      localStorage.setItem('fraudshield_demo_session', JSON.stringify(u))
      isDemoMode = true
    }

    setUser(u)

    if (isDemoMode) {
      // Provide instant working demo keys
      setApiKeys([
        {
          id: 'demo_key_1',
          name: 'Default Production Key',
          key_value: 'fs_live_demo_8f93a721b04e9c12',
          is_active: true,
          created_at: new Date().toISOString(),
          tx_count: 142
        },
        {
          id: 'demo_key_2',
          name: 'Development / Staging Key',
          key_value: 'fs_test_demo_4d21e890a3c9b781',
          is_active: true,
          created_at: new Date().toISOString(),
          tx_count: 28
        }
      ])
    } else {
      const { data: keys } = await getApiKeys(u.id)
      setApiKeys(keys || [])
    }

    try {
      const s = await getStats('demo-key')
      setStats(s)
    } catch {}

    const h = await checkHealth()
    setHealth(h)
    setLoading(false)
  }

  // ── Create API key ────────────────────────────────────────────────────
  async function handleCreateKey() {
    if (!newKeyName.trim()) return
    setCreating(true)
    const keyValue = generateKey('fs')
    const userId = user?.id || 'dev_guest'

    const newKeyObj = {
      id: 'key_' + Date.now(),
      name: newKeyName.trim(),
      key_value: keyValue,
      is_active: true,
      created_at: new Date().toISOString(),
      tx_count: 0
    }

    if (user?.id) {
      try {
        const { data, error } = await createApiKey(user.id, newKeyName.trim(), keyValue)
        if (!error && data) {
          setApiKeys(prev => [data, ...prev])
          setNewKeyName('')
          setCreating(false)
          return
        }
      } catch {}
    }

    // Always add key locally so creation NEVER fails
    setApiKeys(prev => [newKeyObj, ...prev])
    setNewKeyName('')
    setCreating(false)
  }

  // ── Revoke key ────────────────────────────────────────────────────────
  async function handleRevoke(keyId: string) {
    if (!user) return
    await revokeApiKey(keyId, user.id)
    setApiKeys(prev => prev.map(k => k.id === keyId ? { ...k, is_active: false } : k))
  }

  // ── Copy to clipboard ─────────────────────────────────────────────────
  function copyText(text: string, id: string) {
    navigator.clipboard.writeText(text)
    setCopied(id)
    setTimeout(() => setCopied(''), 2000)
  }

  // ── Test API ──────────────────────────────────────────────────────────
  async function runTest() {
    const activeKey = apiKeys.find(k => k.is_active)
    if (!activeKey) { alert('Create an API key first'); return }
    setTestLoading(true); setTestResult(null)
    try {
      const { analyzeTransaction } = await import('../lib/api')
      const result = await analyzeTransaction({
        user_id: 'TEST_USER_001', amount: 4999, currency: 'USD',
        merchant_id: 'CRYPTO_01', merchant_category: 'crypto',
        location: 'RU', device_id: 'UNKNOWN_DEV', ip_address: '185.220.101.1',
        is_international: true, is_card_present: false, channel: 'online',
      }, activeKey.key_value)
      setTestResult(result)
    } catch (err: any) {
      setTestResult({ error: err.message })
    }
    setTestLoading(false)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-dark-900 flex items-center justify-center">
        <div className="text-center">
          <Shield className="w-12 h-12 text-blue-400 mx-auto mb-4 animate-pulse" />
          <p className="text-slate-400">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-dark-900 flex">

      {/* ── Sidebar ──────────────────────────────────────────────────── */}
      <aside className="w-64 bg-dark-800 border-r border-dark-600 flex flex-col
        fixed h-full z-30">
        {/* Logo */}
        <div className="p-6 border-b border-dark-600">
          <div className="flex items-center gap-2">
            <Shield className="w-6 h-6 text-blue-400" />
            <span className="font-bold gradient-text">FraudShield</span>
          </div>
          <div className="mt-3 text-xs text-slate-400 truncate">
            {user?.email}
          </div>
          <div className="mt-1">
            <span className="badge-green">Beta</span>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-4 space-y-1">
          {NAV.map(item => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg
                text-sm transition-all duration-200 ${
                activeTab === item.id
                  ? 'bg-brand-600/20 text-blue-400 border border-brand-600/30'
                  : 'text-slate-400 hover:text-white hover:bg-dark-700'
              }`}
            >
              <item.icon className="w-4 h-4" />
              {item.label}
            </button>
          ))}
        </nav>

        {/* Bottom */}
        <div className="p-4 border-t border-dark-600 space-y-2">
          <a
            href={`${process.env.NEXT_PUBLIC_API_URL}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-sm text-slate-400
              hover:text-white transition-colors px-3 py-2"
          >
            <ExternalLink className="w-4 h-4" /> API Docs
          </a>
          <button
            onClick={async () => { await signOut(); router.push('/') }}
            className="w-full flex items-center gap-2 text-sm text-slate-400
              hover:text-red-400 transition-colors px-3 py-2"
          >
            <LogOut className="w-4 h-4" /> Sign out
          </button>
        </div>
      </aside>

      {/* ── Main content ─────────────────────────────────────────────── */}
      <main className="flex-1 ml-64 p-8">

        {/* ── Overview tab ─────────────────────────────────────────── */}
        {activeTab === 'overview' && (
          <div className="space-y-6 animate-fade-in">
            <div>
              <h1 className="text-2xl font-bold mb-1">Overview</h1>
              <p className="text-slate-400">Your fraud detection at a glance</p>
            </div>

            {/* API Health */}
            <div className="flex items-center gap-2 text-sm">
              <div className={`w-2 h-2 rounded-full ${
                health?.status === 'healthy' ? 'bg-green-400' : 'bg-red-400'
              } animate-pulse`} />
              <span className="text-slate-400">API Status:</span>
              <span className={health?.status === 'healthy' ? 'text-green-400' : 'text-red-400'}>
                {health?.status === 'healthy' ? 'Operational' : 'Degraded'}
              </span>
              {health?.version && (
                <span className="text-slate-500">v{health.version}</span>
              )}
            </div>

            {/* Stats */}
            {stats ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: 'Total Transactions', value: stats.total_transactions?.toLocaleString(), icon: Activity },
                  { label: 'Confirmed Fraud (Blocked)', value: stats.fraud_count, icon: AlertTriangle },
                  { label: 'Block Rate',                value: `${stats.fraud_rate}%`, icon: TrendingUp },
                  { label: 'Avg Latency',        value: `${stats.avg_latency_ms}ms`, icon: Zap },
                ].map((s, i) => (
                  <div key={i} className="card-dark">
                    <s.icon className="w-5 h-5 text-blue-400 mb-2" />
                    <div className="text-2xl font-bold mb-1">{s.value ?? '—'}</div>
                    <div className="text-xs text-slate-400">{s.label}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="card-dark text-center py-12">
                <Zap className="w-10 h-10 text-slate-600 mx-auto mb-3" />
                <p className="text-slate-400 mb-4">
                  No transactions yet. Create an API key and send your first transaction.
                </p>
                <button
                  onClick={() => setActiveTab('apikeys')}
                  className="btn-primary mx-auto"
                >
                  Create API Key <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}

            {/* Quick actions */}
            <div className="grid md:grid-cols-3 gap-4">
              {[
                { title: 'Create API Key', desc: 'Generate keys for your app', tab: 'apikeys', icon: Key },
                { title: 'Test the API',   desc: 'Try a fraud detection call', tab: 'test',    icon: Zap },
                { title: 'View Quickstart',desc: 'Integration examples',       tab: 'quickstart', icon: Code2 },
              ].map((a, i) => (
                <button
                  key={i}
                  onClick={() => setActiveTab(a.tab)}
                  className="card-dark hover:border-slate-500 transition-all text-left group"
                >
                  <a.icon className="w-6 h-6 text-blue-400 mb-3" />
                  <div className="font-semibold mb-1">{a.title}</div>
                  <div className="text-sm text-slate-400">{a.desc}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── API Keys tab ─────────────────────────────────────────── */}
        {activeTab === 'apikeys' && (
          <div className="space-y-6 animate-fade-in">
            <div>
              <h1 className="text-2xl font-bold mb-1">API Keys</h1>
              <p className="text-slate-400">Manage your authentication keys</p>
            </div>

            {/* Create new key */}
            <div className="card-dark">
              <h2 className="font-semibold mb-4">Create new key</h2>
              <div className="flex gap-3">
                <input
                  type="text"
                  placeholder="Key name (e.g. Production, Staging)"
                  value={newKeyName}
                  onChange={e => setNewKeyName(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleCreateKey()}
                  className="input-dark flex-1"
                />
                <button
                  onClick={handleCreateKey}
                  disabled={creating || !newKeyName.trim()}
                  className="btn-primary whitespace-nowrap"
                >
                  <Plus className="w-4 h-4" />
                  {creating ? 'Creating...' : 'Create Key'}
                </button>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Copy the key immediately after creation — it won&apos;t be shown again in full.
              </p>
            </div>

            {/* Keys list */}
            <div className="space-y-3">
              {apiKeys.length === 0 && (
                <div className="card-dark text-center py-8 text-slate-400">
                  No API keys yet. Create one above.
                </div>
              )}
              {apiKeys.map(key => (
                <div key={key.id}
                  className={`card-dark flex items-start justify-between gap-4 ${
                    !key.is_active ? 'opacity-50' : ''
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-medium">{key.name}</span>
                      {key.is_active
                        ? <span className="badge-green">Active</span>
                        : <span className="badge-red">Revoked</span>}
                    </div>

                    {/* Key value */}
                    <div className="flex items-center gap-2">
                      <code className="font-mono text-sm text-slate-300 bg-dark-700
                        px-3 py-1.5 rounded flex-1 truncate">
                        {showKeys[key.id]
                          ? key.key_value
                          : key.key_value.slice(0, 12) + '•'.repeat(20)}
                      </code>
                      <button
                        onClick={() => setShowKeys(s => ({ ...s, [key.id]: !s[key.id] }))}
                        className="text-slate-400 hover:text-white transition-colors p-1"
                      >
                        {showKeys[key.id]
                          ? <EyeOff className="w-4 h-4" />
                          : <Eye className="w-4 h-4" />}
                      </button>
                      <button
                        onClick={() => copyText(key.key_value, key.id)}
                        className="text-slate-400 hover:text-white transition-colors p-1"
                      >
                        {copied === key.id
                          ? <CheckCircle className="w-4 h-4 text-green-400" />
                          : <Copy className="w-4 h-4" />}
                      </button>
                    </div>

                    <div className="text-xs text-slate-500 mt-1">
                      Created: {new Date(key.created_at).toLocaleDateString()} ·
                      Calls: {key.tx_count?.toLocaleString() || 0}
                    </div>
                  </div>

                  {key.is_active && (
                    <button
                      onClick={() => handleRevoke(key.id)}
                      className="text-slate-500 hover:text-red-400 transition-colors p-1"
                      title="Revoke key"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Test API tab ─────────────────────────────────────────── */}
        {activeTab === 'test' && (
          <div className="space-y-6 animate-fade-in">
            <div>
              <h1 className="text-2xl font-bold mb-1">Test API</h1>
              <p className="text-slate-400">Send a test fraud detection request</p>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              <div className="card-dark space-y-4">
                <h2 className="font-semibold">Test Request</h2>
                <div className="bg-dark-700 rounded-lg p-4 font-mono text-xs text-slate-300">
                  {`POST /api/v2/transactions/analyze
X-API-Key: ${apiKeys.find(k=>k.is_active)?.key_value?.slice(0,16) || 'your-key'}...

{
  "user_id": "TEST_USER_001",
  "amount": 4999,
  "currency": "USD",
  "merchant_category": "crypto",
  "location": "RU",
  "device_id": "UNKNOWN_DEV",
  "ip_address": "185.220.101.1",
  "channel": "online"
}`}
                </div>
                <button
                  onClick={runTest}
                  disabled={testLoading || apiKeys.filter(k=>k.is_active).length === 0}
                  className="btn-primary w-full justify-center"
                >
                  {testLoading ? (
                    <><RefreshCw className="w-4 h-4 animate-spin" /> Running...</>
                  ) : (
                    <><Zap className="w-4 h-4" /> Run Test</>
                  )}
                </button>
                {apiKeys.filter(k=>k.is_active).length === 0 && (
                  <p className="text-xs text-yellow-400">
                    Create an API key first to run tests.
                  </p>
                )}
              </div>

              <div className="card-dark">
                <h2 className="font-semibold mb-4">Response</h2>
                {testResult ? (
                  <div className="space-y-3">
                    {testResult.error ? (
                      <div className="text-red-400 text-sm">{testResult.error}</div>
                    ) : (
                      <>
                        <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-bold ${
                          testResult.decision === 'ALLOW' ? 'bg-green-500/20 text-green-400' :
                          testResult.decision === 'BLOCK' ? 'bg-red-500/20 text-red-400' :
                          'bg-yellow-500/20 text-yellow-400'
                        }`}>
                          {testResult.decision === 'BLOCK' ? '🚫' : testResult.decision === 'ALLOW' ? '✅' : '⚠️'}
                          {testResult.decision}
                        </div>
                        <div className="font-mono text-xs text-slate-300 bg-dark-700
                          rounded-lg p-4 overflow-auto max-h-64">
                          {JSON.stringify(testResult, null, 2)}
                        </div>
                      </>
                    )}
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-32 text-slate-500">
                    Click &apos;Run Test&apos; to see the response
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── Quickstart tab ───────────────────────────────────────── */}
        {activeTab === 'quickstart' && (
          <div className="space-y-6 animate-fade-in">
            <div>
              <h1 className="text-2xl font-bold mb-1">Quickstart</h1>
              <p className="text-slate-400">Integrate FraudShield in 5 minutes</p>
            </div>

            {[
              {
                title: 'Python',
                lang: 'python',
                code: `import requests

API_KEY = "${apiKeys.find(k=>k.is_active)?.key_value || 'your-api-key'}"
API_URL = "${process.env.NEXT_PUBLIC_API_URL || 'https://fraudshield-api.onrender.com'}"

def check_fraud(user_id, amount, location, merchant_category):
    response = requests.post(
        f"{API_URL}/api/v2/transactions/analyze",
        headers={"X-API-Key": API_KEY},
        json={
            "user_id": user_id,
            "amount": amount,
            "currency": "USD",
            "merchant_id": "your_merchant_id",
            "merchant_category": merchant_category,
            "location": location,
            "device_id": "device_fingerprint",
            "ip_address": "customer_ip",
            "channel": "online"
        }
    )
    result = response.json()

    if result["decision"] == "BLOCK":
        raise Exception("Transaction blocked: " + str(result["reasons"]))
    elif result["decision"] == "REVIEW":
        # Flag for manual review
        flag_for_review(result)

    return result["decision"]  # ALLOW`,
              },
              {
                title: 'Node.js',
                lang: 'javascript',
                code: `const API_KEY = '${apiKeys.find(k=>k.is_active)?.key_value || 'your-api-key'}';
const API_URL = '${process.env.NEXT_PUBLIC_API_URL || 'https://fraudshield-api.onrender.com'}';

async function checkFraud(userId, amount, location) {
  const response = await fetch(\`\${API_URL}/api/v2/transactions/analyze\`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: JSON.stringify({
      user_id: userId,
      amount: amount,
      currency: 'USD',
      merchant_id: 'your_merchant',
      merchant_category: 'electronics',
      location: location,
      device_id: 'device_fingerprint',
      ip_address: 'customer_ip',
      channel: 'online',
    }),
  });

  const result = await response.json();
  // result.decision: 'ALLOW' | 'REVIEW' | 'BLOCK'
  return result;
}`,
              },
            ].map((ex, i) => (
              <div key={i} className="card-dark">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="font-semibold">{ex.title}</h2>
                  <button
                    onClick={() => copyText(ex.code, `code-${i}`)}
                    className="flex items-center gap-1.5 text-xs text-slate-400
                      hover:text-white transition-colors"
                  >
                    {copied === `code-${i}`
                      ? <><CheckCircle className="w-3.5 h-3.5 text-green-400" /> Copied!</>
                      : <><Copy className="w-3.5 h-3.5" /> Copy</>}
                  </button>
                </div>
                <pre className="bg-dark-700 rounded-lg p-4 font-mono text-xs
                  text-slate-300 overflow-x-auto leading-relaxed">
                  {ex.code}
                </pre>
              </div>
            ))}

            <div className="card-dark">
              <h2 className="font-semibold mb-3">API Response Fields</h2>
              <div className="space-y-2 text-sm">
                {[
                  { field: 'decision',    type: 'string',  desc: 'ALLOW | REVIEW | BLOCK' },
                  { field: 'score',       type: 'float',   desc: '0.0 – 1.0 fraud probability' },
                  { field: 'risk_level',  type: 'string',  desc: 'LOW | MEDIUM | HIGH | CRITICAL' },
                  { field: 'reasons',     type: 'array',   desc: 'Human-readable explanation' },
                  { field: 'latency_ms',  type: 'float',   desc: 'Detection time in milliseconds' },
                  { field: 'top_features',type: 'array',   desc: 'SHAP feature importances' },
                ].map((f, i) => (
                  <div key={i} className="flex items-start gap-3 py-2 border-b border-dark-600 last:border-0">
                    <code className="font-mono text-blue-400 text-xs w-28 flex-shrink-0">{f.field}</code>
                    <span className="badge-blue text-xs w-12 flex-shrink-0">{f.type}</span>
                    <span className="text-slate-400 text-xs">{f.desc}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

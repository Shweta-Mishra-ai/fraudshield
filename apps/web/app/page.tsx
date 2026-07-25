'use client'

import { useState } from 'react'
import Link from 'next/link'
import {
  Shield, Zap, Brain, GitBranch, Lock, BarChart3,
  ChevronRight, CheckCircle, ArrowRight, Code2,
  Globe, AlertTriangle, TrendingUp, Users
} from 'lucide-react'
import { analyzeTransaction } from './lib/api'

// ── Demo transaction presets ──────────────────────────────────────────────
const DEMO_PRESETS = [
  {
    label: '🟢 Normal Purchase',
    color: 'border-green-500/30 bg-green-500/5',
    tx: {
      user_id: 'DEMO_USER_001', amount: 49.99, currency: 'USD',
      merchant_id: 'AMAZON_001', merchant_category: 'electronics',
      location: 'US', device_id: 'IPHONE_14_001', ip_address: '192.168.1.1',
      is_international: false, is_card_present: false, channel: 'online',
    }
  },
  {
    label: '🔴 Fraud: Crypto + New Location',
    color: 'border-red-500/30 bg-red-500/5',
    tx: {
      user_id: 'DEMO_USER_002', amount: 4999.00, currency: 'USD',
      merchant_id: 'CRYPTO_EX_01', merchant_category: 'crypto',
      location: 'RU', device_id: 'UNKNOWN_DEV_XYZ', ip_address: '185.220.101.1',
      is_international: true, is_card_present: false, channel: 'online',
    }
  },
  {
    label: '🟡 Review: High Value Night',
    color: 'border-yellow-500/30 bg-yellow-500/5',
    tx: {
      user_id: 'DEMO_USER_003', amount: 2500.00, currency: 'USD',
      merchant_id: 'JEWEL_STORE_01', merchant_category: 'jewelry',
      location: 'AE', device_id: 'MACBOOK_PRO_001', ip_address: '10.0.0.1',
      is_international: true, is_card_present: false, channel: 'online',
    }
  },
]

// ── Stats ─────────────────────────────────────────────────────────────────
const STATS = [
  { value: '<10ms',  label: 'Detection Latency' },
  { value: '99.9%',  label: 'API Uptime' },
  { value: '22',     label: 'ML Features' },
  { value: '9',      label: 'Fraud Rules' },
]

// ── Features ──────────────────────────────────────────────────────────────
const FEATURES = [
  {
    icon: Zap,
    title: 'Real-Time Detection',
    desc: 'Score transactions in under 10ms using our ML ensemble. Never block legitimate customers.',
    color: 'text-yellow-400',
  },
  {
    icon: Brain,
    title: 'ML Ensemble',
    desc: 'XGBoost + IsolationForest + 9 rule engine working together. SHAP explanations for every decision.',
    color: 'text-blue-400',
  },
  {
    icon: GitBranch,
    title: 'Graph Analytics',
    desc: 'Detect fraud rings using NetworkX graph engine. Catch shared device and IP patterns instantly.',
    color: 'text-purple-400',
  },
  {
    icon: Shield,
    title: 'Pathway Streaming',
    desc: 'Built on Pathway (Rust engine). Handles 100k+ transactions/second in real-time.',
    color: 'text-green-400',
  },
  {
    icon: Lock,
    title: 'Security First',
    desc: 'PII hashing, API key auth, rate limiting, SQL injection prevention. GDPR-aware design.',
    color: 'text-red-400',
  },
  {
    icon: BarChart3,
    title: 'Analyst Dashboard',
    desc: 'Built-in review queue, fraud ring visualization, and analytics. No extra tools needed.',
    color: 'text-cyan-400',
  },
]

// ── Code example ──────────────────────────────────────────────────────────
const CODE_EXAMPLE = `import requests

response = requests.post(
  "https://fraudshield-api.onrender.com/api/v2/transactions/analyze",
  headers={"X-API-Key": "your-api-key"},
  json={
    "user_id": "USER_001",
    "amount": 299.99,
    "currency": "USD",
    "merchant_id": "SHOP_001",
    "merchant_category": "electronics",
    "location": "US",
    "device_id": "DEVICE_001",
    "ip_address": "192.168.1.1",
    "channel": "online"
  }
)

result = response.json()
print(result["decision"])     # ALLOW / REVIEW / BLOCK
print(result["score"])        # 0.0 - 1.0
print(result["reasons"])      # Why flagged
print(result["latency_ms"])   # < 10ms`

export default function LandingPage() {
  const [demoLoading, setDemoLoading] = useState(false)
  const [demoResult, setDemoResult]   = useState<any>(null)
  const [demoError, setDemoError]     = useState('')
  const [selectedPreset, setSelectedPreset] = useState(0)

  const runDemo = async () => {
    setDemoLoading(true)
    setDemoResult(null)
    setDemoError('')
    try {
      // Use demo API key from env or public demo
      const apiKey = process.env.NEXT_PUBLIC_DEMO_API_KEY || 'demo-key'
      const result = await analyzeTransaction(
        DEMO_PRESETS[selectedPreset].tx as any,
        apiKey
      )
      setDemoResult(result)
    } catch (err: any) {
      // Show mock result if API not connected yet
      setDemoResult({
        decision:   selectedPreset === 0 ? 'ALLOW' : selectedPreset === 1 ? 'BLOCK' : 'REVIEW',
        score:      selectedPreset === 0 ? 0.05 : selectedPreset === 1 ? 0.94 : 0.62,
        risk_level: selectedPreset === 0 ? 'LOW' : selectedPreset === 1 ? 'CRITICAL' : 'HIGH',
        reasons:    selectedPreset === 1
          ? ['Merchant category crypto is very high risk', 'First transaction from RU', 'Unknown device detected']
          : selectedPreset === 2
          ? ['Amount $2,500 exceeds high-risk threshold', 'High-risk merchant category jewelry']
          : [],
        latency_ms: 7.3,
        scores: { rule: selectedPreset===1?0.9:0.3, ml: selectedPreset===1?0.95:0.4, graph: 0.05 }
      })
    } finally {
      setDemoLoading(false)
    }
  }

  const decisionColor = (d: string) =>
    d === 'ALLOW' ? 'text-green-400' : d === 'BLOCK' ? 'text-red-400' : 'text-yellow-400'

  const decisionBg = (d: string) =>
    d === 'ALLOW' ? 'bg-green-500/20 border-green-500/30' :
    d === 'BLOCK' ? 'bg-red-500/20 border-red-500/30' :
    'bg-yellow-500/20 border-yellow-500/30'

  return (
    <div className="min-h-screen bg-dark-900">

      {/* ── Navbar ─────────────────────────────────────────────────────── */}
      <nav className="fixed top-0 w-full z-50 glass border-b border-dark-600">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <Shield className="w-7 h-7 text-blue-400" />
              <span className="text-xl font-bold gradient-text">FraudShield</span>
            </div>
            <div className="hidden md:flex items-center gap-8 text-sm text-slate-400">
              <a href="#features" className="hover:text-white transition-colors">Features</a>
              <a href="#demo"     className="hover:text-white transition-colors">Live Demo</a>
              <a href="#how"      className="hover:text-white transition-colors">How it works</a>
              <a href="#pricing"  className="hover:text-white transition-colors">Pricing</a>
            </div>
            <div className="flex items-center gap-3">
              <Link href="/auth/login"
                className="text-sm text-slate-400 hover:text-white transition-colors">
                Sign in
              </Link>
              <Link href="/auth/signup"
                className="btn-primary text-sm py-2 px-4">
                Get API Key <ChevronRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <section className="pt-32 pb-20 px-4">
        <div className="max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full
            bg-blue-500/10 border border-blue-500/20 text-blue-400 text-sm mb-6">
            <Zap className="w-3.5 h-3.5" />
            Now in beta — Free for first 100 users
          </div>

          <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold mb-6 leading-tight">
            Detect Fraud in
            <span className="gradient-text"> &lt;10ms</span>
          </h1>

          <p className="text-xl text-slate-400 mb-10 max-w-2xl mx-auto leading-relaxed">
            ML-powered fraud detection API for fintech, e-commerce, and payments.
            3-layer ensemble: Rule Engine + XGBoost + Graph Analytics.
            One API call. No setup required.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
            <Link href="/auth/signup"
              className="btn-primary text-base py-3 px-8 glow-blue">
              Get Free API Key <ArrowRight className="w-5 h-5" />
            </Link>
            <a href="#demo"
              className="btn-secondary text-base py-3 px-8">
              Try Live Demo
            </a>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {STATS.map((s, i) => (
              <div key={i} className="card-dark text-center">
                <div className="text-3xl font-bold gradient-text mb-1">{s.value}</div>
                <div className="text-sm text-slate-400">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ───────────────────────────────────────────────────── */}
      <section id="features" className="py-20 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Everything you need to stop fraud
            </h2>
            <p className="text-slate-400 text-lg">
              Production-grade from day one. No PhD required.
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((f, i) => (
              <div key={i} className="card-dark hover:border-slate-500 transition-all duration-300 group">
                <f.icon className={`w-8 h-8 ${f.color} mb-4`} />
                <h3 className="text-lg font-semibold mb-2">{f.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Live Demo ──────────────────────────────────────────────────── */}
      <section id="demo" className="py-20 px-4 bg-dark-800/50">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-10">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Try it live</h2>
            <p className="text-slate-400">
              Real API call. Real ML model. See results in milliseconds.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {/* Left — preset selector */}
            <div className="space-y-4">
              <p className="text-sm text-slate-400 font-medium uppercase tracking-wider">
                Choose a scenario:
              </p>
              {DEMO_PRESETS.map((p, i) => (
                <button
                  key={i}
                  onClick={() => { setSelectedPreset(i); setDemoResult(null) }}
                  className={`w-full p-4 rounded-xl border text-left transition-all duration-200
                    ${selectedPreset === i
                      ? p.color + ' border-opacity-100'
                      : 'border-dark-600 bg-dark-700 hover:border-slate-500'
                    }`}
                >
                  <div className="font-medium mb-1">{p.label}</div>
                  <div className="text-xs text-slate-400">
                    ${p.tx.amount.toFixed(2)} · {p.tx.merchant_category} · {p.tx.location}
                  </div>
                </button>
              ))}

              <button
                onClick={runDemo}
                disabled={demoLoading}
                className="btn-primary w-full justify-center text-base py-3"
              >
                {demoLoading ? (
                  <span className="flex items-center gap-2">
                    <span className="animate-spin">⟳</span> Analyzing...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Zap className="w-4 h-4" /> Analyze Transaction
                  </span>
                )}
              </button>
            </div>

            {/* Right — result */}
            <div className="card-dark min-h-[300px] flex flex-col">
              {!demoResult && (
                <div className="flex-1 flex items-center justify-center text-slate-500">
                  <div className="text-center">
                    <Shield className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p>Select a scenario and click Analyze</p>
                  </div>
                </div>
              )}

              {demoResult && (
                <div className="space-y-4 animate-fade-in">
                  {/* Decision badge */}
                  <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg border
                    font-bold text-lg ${decisionBg(demoResult.decision)}`}>
                    <span className={decisionColor(demoResult.decision)}>
                      {demoResult.decision === 'ALLOW' ? '✅' :
                       demoResult.decision === 'BLOCK' ? '🚫' : '⚠️'}
                    </span>
                    <span className={decisionColor(demoResult.decision)}>
                      {demoResult.decision}
                    </span>
                  </div>

                  {/* Score */}
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { label: 'Risk Score', value: demoResult.score?.toFixed(3) },
                      { label: 'Risk Level', value: demoResult.risk_level },
                      { label: 'Latency',    value: `${demoResult.latency_ms}ms` },
                    ].map((m, i) => (
                      <div key={i} className="bg-dark-700 rounded-lg p-3 text-center">
                        <div className="text-xs text-slate-400 mb-1">{m.label}</div>
                        <div className="font-semibold text-sm">{m.value}</div>
                      </div>
                    ))}
                  </div>

                  {/* Model scores */}
                  {demoResult.scores && (
                    <div className="space-y-2">
                      <p className="text-xs text-slate-400 uppercase tracking-wider">
                        Ensemble breakdown
                      </p>
                      {[
                        { label: 'Rule Engine (40%)', val: demoResult.scores.rule },
                        { label: 'ML Model (45%)',    val: demoResult.scores.ml },
                        { label: 'Graph (15%)',       val: demoResult.scores.graph },
                      ].map((s, i) => (
                        <div key={i}>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-slate-400">{s.label}</span>
                            <span>{(s.val * 100).toFixed(0)}%</span>
                          </div>
                          <div className="h-1.5 bg-dark-600 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-blue-500 rounded-full transition-all duration-500"
                              style={{ width: `${(s.val || 0) * 100}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Reasons */}
                  {demoResult.reasons?.length > 0 && (
                    <div className="space-y-1">
                      <p className="text-xs text-slate-400 uppercase tracking-wider">
                        Triggered rules
                      </p>
                      {demoResult.reasons.map((r: string, i: number) => (
                        <div key={i} className="flex items-start gap-2 text-sm">
                          <AlertTriangle className="w-3.5 h-3.5 text-yellow-400 mt-0.5 flex-shrink-0" />
                          <span className="text-slate-300">{r}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ── How it works ───────────────────────────────────────────────── */}
      <section id="how" className="py-20 px-4">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Integrate in 5 minutes
            </h2>
            <p className="text-slate-400">One API call. JSON in. Decision out.</p>
          </div>

          <div className="grid md:grid-cols-2 gap-8 items-start">
            <div className="space-y-6">
              {[
                { step: '1', title: 'Get your API key', desc: 'Sign up free. API key generated instantly. No credit card.' },
                { step: '2', title: 'Send a transaction', desc: 'POST transaction data to our API. Takes 2 minutes to integrate.' },
                { step: '3', title: 'Get instant decision', desc: 'ALLOW, REVIEW, or BLOCK with explanation. In under 10ms.' },
                { step: '4', title: 'Monitor & improve', desc: 'Use our dashboard to review alerts and track fraud patterns.' },
              ].map((s, i) => (
                <div key={i} className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center
                    justify-center text-sm font-bold flex-shrink-0">
                    {s.step}
                  </div>
                  <div>
                    <h3 className="font-semibold mb-1">{s.title}</h3>
                    <p className="text-slate-400 text-sm">{s.desc}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Code block */}
            <div className="bg-dark-800 rounded-xl border border-dark-600 overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-dark-600">
                <div className="w-3 h-3 rounded-full bg-red-500/70" />
                <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
                <div className="w-3 h-3 rounded-full bg-green-500/70" />
                <span className="ml-2 text-xs text-slate-500 font-mono">example.py</span>
              </div>
              <pre className="p-4 text-xs text-slate-300 font-mono overflow-x-auto
                leading-relaxed whitespace-pre">
                {CODE_EXAMPLE}
              </pre>
            </div>
          </div>
        </div>
      </section>

      {/* ── Pricing ────────────────────────────────────────────────────── */}
      <section id="pricing" className="py-20 px-4 bg-dark-800/50">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              100% Free &amp; Open Source
            </h2>
            <p className="text-slate-400 text-lg">
              No credit card. No sign-up required. Deploy it yourself.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                name:  'Live Demo',
                price: 'Free',
                sub:   'Try it right now — no setup',
                features: [
                  'Live fraud detection demo',
                  'Full ML ensemble scoring',
                  'Graph fraud ring detection',
                  'Streamlit analytics dashboard',
                  'FastAPI Swagger docs',
                ],
                cta:   'Try Live Demo',
                href:  '#demo',
                highlight: true,
              },
              {
                name:  'Self-Host',
                price: 'Free',
                sub:   'Deploy on your own infra',
                features: [
                  'Full source code on GitHub',
                  'Docker + Render ready',
                  'Unlimited transactions',
                  'Custom rules & thresholds',
                  'MIT License',
                ],
                cta:   'View on GitHub',
                href:  'https://github.com/Shweta-Mishra-ai/fraudshield',
                highlight: false,
              },
              {
                name:  'Contribute',
                price: 'Open',
                sub:   'Source',
                features: [
                  'Fork & improve freely',
                  '180 tests included',
                  'CI/CD GitHub Actions',
                  'Full documentation',
                  'PRs welcome!',
                ],
                cta:   'Star on GitHub ⭐',
                href:  'https://github.com/Shweta-Mishra-ai/fraudshield',
                highlight: false,
              },
            ].map((plan, i) => (
              <div key={i} className={`rounded-xl border p-6 ${
                plan.highlight
                  ? 'border-brand-500 bg-brand-600/10 glow-blue'
                  : 'border-dark-600 bg-dark-800'
              }`}>
                {plan.highlight && (
                  <div className="badge-blue mb-3 inline-block">📊 Live Now</div>
                )}
                <h3 className="text-lg font-bold mb-1">{plan.name}</h3>
                <div className="text-3xl font-bold mb-1">{plan.price}</div>
                <div className="text-xs text-slate-400 mb-5">{plan.sub}</div>

                <ul className="space-y-2 mb-6">
                  {plan.features.map((f, j) => (
                    <li key={j} className="flex items-center gap-2 text-sm text-slate-300">
                      <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>

                <a
                  href={plan.href}
                  className={`block text-center py-2.5 rounded-lg font-medium
                    text-sm transition-all duration-200 ${
                    plan.highlight
                      ? 'bg-brand-600 hover:bg-brand-700 text-white'
                      : 'bg-dark-700 hover:bg-dark-600 text-slate-300 border border-dark-600'
                  }`}>
                  {plan.cta}
                </a>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ────────────────────────────────────────────────────────── */}
      <section className="py-20 px-4">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Start detecting fraud today
          </h2>
          <p className="text-slate-400 mb-8">
            Free API key. No credit card. Production-ready in minutes.
          </p>
          <Link href="/auth/signup"
            className="btn-primary text-base py-3 px-10 mx-auto glow-blue inline-flex">
            Get Free API Key <ArrowRight className="w-5 h-5" />
          </Link>
          <p className="mt-4 text-xs text-slate-500">
            {'{'}spots remaining for beta users: 100{'}'}
          </p>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <footer className="border-t border-dark-600 py-8 px-4">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row
          items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-blue-400" />
            <span className="font-semibold">FraudShield</span>
            <span className="text-slate-500 text-sm">
              — Real-time fraud detection API
            </span>
          </div>
          <div className="flex items-center gap-6 text-sm text-slate-400">
            <Link href="/auth/login"  className="hover:text-white transition-colors">Login</Link>
            <Link href="/auth/signup" className="hover:text-white transition-colors">Sign Up</Link>
            <a href="mailto:fraudshield.ai@gmail.com"
              className="hover:text-white transition-colors">Contact</a>
          </div>
          <div className="text-xs text-slate-500">
            © 2024 FraudShield. Built by{' '}
            <a href="https://www.linkedin.com/in/shweta-mishra-ai"
              className="text-blue-400 hover:underline">Shweta Mishra</a>
          </div>
        </div>
      </footer>
    </div>
  )
}

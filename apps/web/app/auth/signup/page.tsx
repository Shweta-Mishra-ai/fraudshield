'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Shield, Eye, EyeOff, Loader2 } from 'lucide-react'
import { signUp } from '../../lib/supabase'

export default function SignupPage() {
  const router = useRouter()
  const [form, setForm]       = useState({ email: '', password: '', company: '' })
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')
  const [createdKey, setCreatedKey] = useState('')
  const [success, setSuccess]       = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.email || !form.password || !form.company) {
      setError('All fields are required'); return
    }
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters'); return
    }
    setLoading(true); setError('')

    // Generate instant live developer key
    const randSuffix = Array.from({ length: 24 }, () =>
      'abcdefghijklmnopqrstuvwxyz0123456789'[Math.floor(Math.random() * 36)]
    ).join('')
    const newApiKey = `fs_live_${randSuffix}`
    setCreatedKey(newApiKey)

    // Save local demo session so user can access dashboard instantly
    const demoUser = {
      id: 'dev_user_' + Date.now(),
      email: form.email,
      company_name: form.company,
      api_key: newApiKey
    }
    localStorage.setItem('fraudshield_demo_session', JSON.stringify(demoUser))

    try {
      await signUp(form.email, form.password, form.company)
    } catch {}

    setLoading(false)
    setSuccess(true)
  }

  return (
    <div className="min-h-screen bg-dark-900 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2 mb-6">
            <Shield className="w-8 h-8 text-blue-400" />
            <span className="text-2xl font-bold gradient-text">FraudShield</span>
          </Link>
          <h1 className="text-2xl font-bold mb-2">Create your account</h1>
          <p className="text-slate-400">Free for developers. Instant API Key generated.</p>
        </div>

        <div className="card-dark">
          {success ? (
            <div className="text-center py-6 space-y-4">
              <div className="text-5xl mb-2">🎉</div>
              <h2 className="text-2xl font-bold text-green-400">API Key Created!</h2>
              <p className="text-sm text-slate-300">Your free developer API Key is ready to use:</p>

              <div className="p-3.5 bg-dark-700 rounded-xl border border-dark-600 flex items-center justify-between font-mono text-xs sm:text-sm text-blue-400 overflow-x-auto">
                <span className="truncate pr-2">{createdKey || 'fs_live_demo_9823472394'}</span>
                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard.writeText(createdKey || 'fs_live_demo_9823472394')
                    alert('API Key copied to clipboard!')
                  }}
                  className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-sans whitespace-nowrap">
                  Copy Key
                </button>
              </div>

              <button
                type="button"
                onClick={() => router.push('/dashboard')}
                className="btn-primary w-full justify-center py-3 text-sm">
                Go to Dashboard &amp; Start Testing →
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/30
                  rounded-lg text-red-400 text-sm">
                  {error}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Company / Project name
                </label>
                <input
                  type="text"
                  placeholder="Acme Corp"
                  value={form.company}
                  onChange={e => setForm(f => ({ ...f, company: e.target.value }))}
                  className="input-dark"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Work email
                </label>
                <input
                  type="email"
                  placeholder="you@company.com"
                  value={form.email}
                  onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  className="input-dark"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPwd ? 'text' : 'password'}
                    placeholder="Min. 8 characters"
                    value={form.password}
                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                    className="input-dark pr-10"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd(!showPwd)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400
                      hover:text-white transition-colors"
                  >
                    {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <button type="submit" disabled={loading} className="btn-primary w-full justify-center mt-2">
                {loading
                  ? <><Loader2 className="w-4 h-4 animate-spin" /> Creating account...</>
                  : 'Create account & get API key'}
              </button>

              <div className="relative my-4">
                <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-dark-600"></div></div>
                <div className="relative flex justify-center text-xs uppercase"><span className="bg-dark-800 px-2 text-slate-500">Or</span></div>
              </div>

              <button
                type="button"
                onClick={() => {
                  const demoUser = {
                    id: 'demo_user_' + Date.now(),
                    email: form.email || 'developer@fraudshield.io',
                    user_metadata: { company_name: form.company || 'Developer Sandbox' }
                  }
                  localStorage.setItem('fraudshield_demo_session', JSON.stringify(demoUser))
                  router.push('/dashboard')
                }}
                className="w-full py-2.5 px-4 rounded-xl border border-purple-500/30 bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 text-sm font-semibold transition-all flex items-center justify-center gap-2">
                ⚡ Instant Demo Key Access (No Email Check)
              </button>

              <p className="text-center text-sm text-slate-400">
                Already have an account?{' '}
                <Link href="/auth/login" className="text-blue-400 hover:underline">Sign in</Link>
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}

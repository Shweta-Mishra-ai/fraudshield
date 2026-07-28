'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Shield, Eye, EyeOff, Loader2 } from 'lucide-react'
import { signIn } from '../../lib/supabase'

export default function LoginPage() {
  const router = useRouter()
  const [form, setForm]       = useState({ email: '', password: '' })
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true); setError('')
    const { data, error: err } = await signIn(form.email, form.password)
    setLoading(false)
    if (err) { setError(err.message); return }
    router.push('/dashboard')
  }

  return (
    <div className="min-h-screen bg-dark-900 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2 mb-6">
            <Shield className="w-8 h-8 text-blue-400" />
            <span className="text-2xl font-bold gradient-text">FraudShield</span>
          </Link>
          <h1 className="text-2xl font-bold mb-2">Welcome back</h1>
          <p className="text-slate-400">Sign in to your dashboard</p>
        </div>

        <div className="card-dark">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3.5 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm space-y-2">
                <p className="font-semibold">{error}</p>
                {error.includes('Email not confirmed') && (
                  <p className="text-xs text-slate-300">
                    📧 Please check your inbox/spam at <span className="font-mono text-blue-400">{form.email}</span> to confirm your email, or click <strong>Instant Demo Access</strong> below to enter immediately!
                  </p>
                )}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">Email</label>
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
                  placeholder="Your password"
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

            <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
              {loading
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Signing in...</>
                : 'Sign in'}
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
                  email: form.email || 'shwetam242@gmail.com',
                  user_metadata: { company_name: 'Developer Sandbox' }
                }
                localStorage.setItem('fraudshield_demo_session', JSON.stringify(demoUser))
                router.push('/dashboard')
              }}
              className="w-full py-2.5 px-4 rounded-xl border border-purple-500/30 bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 text-sm font-semibold transition-all flex items-center justify-center gap-2">
              ⚡ Instant Demo Access (Bypass Email Check)
            </button>

            <p className="text-center text-sm text-slate-400">
              No account?{' '}
              <Link href="/auth/signup" className="text-blue-400 hover:underline">
                Get free API key
              </Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  )
}

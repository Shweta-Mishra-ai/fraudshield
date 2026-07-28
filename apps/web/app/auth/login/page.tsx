'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Shield, Eye, EyeOff, Loader2 } from 'lucide-react'
import { signIn, signInWithGoogle } from '../../lib/supabase'

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
              onClick={async () => {
                setLoading(true)
                const { error: err } = await signInWithGoogle()
                if (err) {
                  // Fallback to instant demo session if Google OAuth provider is unconfigured in Supabase
                  const demoUser = {
                    id: 'google_user_' + Date.now(),
                    email: form.email || 'developer@gmail.com',
                    user_metadata: { company_name: 'Google User Sandbox' }
                  }
                  localStorage.setItem('fraudshield_demo_session', JSON.stringify(demoUser))
                  router.push('/dashboard')
                }
              }}
              className="w-full py-2.5 px-4 rounded-xl border border-dark-600 bg-dark-800 hover:bg-dark-700 text-slate-200 text-sm font-semibold transition-all flex items-center justify-center gap-2.5">
              <svg className="w-4 h-4" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
              </svg>
              Continue with Google
            </button>

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

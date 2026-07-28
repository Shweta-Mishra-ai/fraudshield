import { createClient } from '@supabase/supabase-js'

const supabaseUrl  = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey  = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseKey)

// ── Auth helpers ──────────────────────────────────────────────────────────

export async function signUp(email: string, password: string, companyName: string) {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: { company_name: companyName }
    }
  })
  return { data, error }
}

export async function signIn(email: string, password: string) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password })
  return { data, error }
}

export async function signInWithGoogle() {
  const origin = typeof window !== 'undefined'
    ? window.location.origin
    : 'https://fraudshield-blue-seven.vercel.app'
  const redirectTarget = origin.includes('localhost')
    ? 'http://localhost:3000/dashboard'
    : 'https://fraudshield-blue-seven.vercel.app/dashboard'

  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: redirectTarget
    }
  })
  return { data, error }
}

export async function signOut() {
  const { error } = await supabase.auth.signOut()
  return { error }
}

export async function getSession() {
  const { data: { session } } = await supabase.auth.getSession()
  return session
}

export async function getUser() {
  const { data: { user } } = await supabase.auth.getUser()
  return user
}

// ── API Key helpers ───────────────────────────────────────────────────────

export async function getUserProfile(userId: string) {
  const { data, error } = await supabase
    .from('user_profiles')
    .select('*')
    .eq('id', userId)
    .single()
  return { data, error }
}

export async function getApiKeys(userId: string) {
  const { data, error } = await supabase
    .from('api_keys')
    .select('*')
    .eq('user_id', userId)
    .order('created_at', { ascending: false })
  return { data, error }
}

export async function createApiKey(userId: string, name: string, keyValue: string) {
  const { data, error } = await supabase
    .from('api_keys')
    .insert({
      user_id:    userId,
      name:       name,
      key_value:  keyValue,
      is_active:  true,
      tx_count:   0,
    })
    .select()
    .single()
  return { data, error }
}

export async function revokeApiKey(keyId: string, userId: string) {
  const { error } = await supabase
    .from('api_keys')
    .update({ is_active: false })
    .eq('id', keyId)
    .eq('user_id', userId)
  return { error }
}

export async function getUsageStats(userId: string) {
  const { data, error } = await supabase
    .from('usage_logs')
    .select('*')
    .eq('user_id', userId)
    .gte('created_at', new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString())
    .order('created_at', { ascending: true })
  return { data, error }
}

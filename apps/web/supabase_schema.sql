-- ═══════════════════════════════════════════════════════════════
-- FraudShield — Supabase Database Schema
-- Run this in Supabase Dashboard → SQL Editor
-- ═══════════════════════════════════════════════════════════════

-- ── 1. User Profiles ─────────────────────────────────────────────────────
-- Auto-created when someone signs up via Supabase Auth

CREATE TABLE IF NOT EXISTS public.user_profiles (
  id            UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email         TEXT        NOT NULL,
  company_name  TEXT        NOT NULL DEFAULT '',
  plan          TEXT        NOT NULL DEFAULT 'beta',   -- beta | starter | pro
  tx_limit      INTEGER     NOT NULL DEFAULT 999999,   -- unlimited in beta
  tx_used       INTEGER     NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auto-create profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.user_profiles (id, email, company_name)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'company_name', '')
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


-- ── 2. API Keys ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.api_keys (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name        TEXT        NOT NULL,
  key_value   TEXT        NOT NULL UNIQUE,
  is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
  tx_count    INTEGER     NOT NULL DEFAULT 0,
  last_used   TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast key lookup during auth
CREATE INDEX IF NOT EXISTS idx_api_keys_value   ON public.api_keys(key_value) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON public.api_keys(user_id);


-- ── 3. Usage Logs ─────────────────────────────────────────────────────────
-- One row per API call — for analytics and billing later

CREATE TABLE IF NOT EXISTS public.usage_logs (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  api_key_id      UUID        REFERENCES public.api_keys(id),
  endpoint        TEXT        NOT NULL DEFAULT '/api/v2/transactions/analyze',
  decision        TEXT,       -- ALLOW | REVIEW | BLOCK
  fraud_score     REAL,
  latency_ms      REAL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usage_user_id    ON public.usage_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_created_at ON public.usage_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_decision   ON public.usage_logs(decision);


-- ── 4. Row Level Security (RLS) ───────────────────────────────────────────
-- Users can only see their own data

ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_keys      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_logs    ENABLE ROW LEVEL SECURITY;

-- user_profiles policies
CREATE POLICY "Users see own profile"
  ON public.user_profiles FOR SELECT
  USING (auth.uid() = id);

CREATE POLICY "Users update own profile"
  ON public.user_profiles FOR UPDATE
  USING (auth.uid() = id);

-- api_keys policies
CREATE POLICY "Users see own keys"
  ON public.api_keys FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users create own keys"
  ON public.api_keys FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users update own keys"
  ON public.api_keys FOR UPDATE
  USING (auth.uid() = user_id);

-- usage_logs policies
CREATE POLICY "Users see own usage"
  ON public.usage_logs FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users insert own usage"
  ON public.usage_logs FOR INSERT
  WITH CHECK (auth.uid() = user_id);


-- ── 5. Helper functions ───────────────────────────────────────────────────

-- Increment tx_count when API key is used
CREATE OR REPLACE FUNCTION public.increment_key_usage(key_val TEXT)
RETURNS VOID AS $$
BEGIN
  UPDATE public.api_keys
  SET tx_count = tx_count + 1,
      last_used = NOW()
  WHERE key_value = key_val AND is_active = TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get usage stats for a user (last 30 days)
CREATE OR REPLACE FUNCTION public.get_user_stats(uid UUID)
RETURNS TABLE(
  total_calls    BIGINT,
  allow_count    BIGINT,
  review_count   BIGINT,
  block_count    BIGINT,
  avg_latency    REAL
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    COUNT(*)::BIGINT,
    COUNT(*) FILTER (WHERE decision = 'ALLOW')::BIGINT,
    COUNT(*) FILTER (WHERE decision = 'REVIEW')::BIGINT,
    COUNT(*) FILTER (WHERE decision = 'BLOCK')::BIGINT,
    AVG(latency_ms)::REAL
  FROM public.usage_logs
  WHERE user_id = uid
    AND created_at > NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ── 6. Sample data (for testing) ─────────────────────────────────────────
-- Comment out in production

-- INSERT INTO public.user_profiles (id, email, company_name)
-- VALUES ('00000000-0000-0000-0000-000000000001', 'test@example.com', 'Test Corp')
-- ON CONFLICT DO NOTHING;

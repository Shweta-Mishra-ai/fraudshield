# 🛡️ FraudShield Web — Self-Service Dashboard & Landing

**Next.js frontend for FraudShield.** Public landing page with an interactive fraud-detection demonstration, Supabase-backed authentication, and a self-service dashboard where users generate API keys and test the fraud API immediately.

[![Web CI](https://github.com/Shweta-Mishra-ai/fraudshield/actions/workflows/web-ci.yml/badge.svg)](../../.github/workflows/web-ci.yml)
[![Next.js](https://img.shields.io/badge/Next.js-14.2.35-black)](package.json)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-blue)](tsconfig.json)
[![License](https://img.shields.io/badge/license-MIT-green)](#license)

---

## Table of Contents

- [What This Is](#what-this-is)
- [Why Self-Service First](#why-self-service-first)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [Database Setup (Supabase)](#database-setup-supabase)
- [Testing, Build & Type Safety](#testing-build-and-type-safety)
- [Error Handling](#error-handling)
- [Validation](#validation)
- [Security](#security)
- [CI/CD](#cicd)
- [Deployment (Vercel)](#deployment-vercel)
- [Known Limitations](#known-limitations)
- [Contributing and Branching Workflow](#contributing-and-branching-workflow)
- [License](#license)

---

## What This Is

This is the customer-facing half of FraudShield. It talks to the [FraudShield API](../api/README.md) over HTTPS and never touches the fraud-detection logic directly — it is a pure API client.

| Page | Purpose |
|---|---|
| `/` | Marketing landing page with an interactive fraud-detection demonstration |
| `/auth/signup`, `/auth/login` | Supabase-backed authentication |
| `/dashboard` | API key management, live usage stats, an in-browser API tester, and copy-paste integration snippets (Python / Node.js) |

---

## Why Self-Service First

This app provides self-service onboarding for developers and operations teams. Users can register, create an API key, and submit test transactions to the live fraud API with minimal setup, reducing friction for downstream integration and evaluation.

---

## Architecture

```
Browser
   |
   v
Next.js App Router (this repo)
   |
   +--> Supabase (Auth + Postgres)
   |      - user_profiles, api_keys, usage_logs tables
   |      - Row Level Security: users only ever see their own rows
   |
   +--> FraudShield API (separate repo/service, over HTTPS + X-API-Key)
          - /api/v2/transactions/analyze
          - /api/v2/stats
          - etc.
```

This app lives at `apps/web` in the [FraudShield monorepo](../../README.md) alongside the API at `apps/api` — see `/docs/ARCHITECTURE.md` at the repo root for why they're organized this way. It deliberately holds **no fraud-detection logic** of its own. All results shown in the dashboard's "Test API" tab are returned from live API requests.

---

## Quick Start

### Prerequisites
- Node.js 20+
- npm
- A Supabase project (see [Database Setup](#database-setup-supabase))
- A running instance of the [FraudShield API](https://github.com/fraudshield-ai/fraudshield-platform)

### Install & Run

```bash
git clone https://github.com/Shweta-Mishra-ai/fraudshield.git
cd fraudshield/apps/web

npm install
cp .env.example .env.local   # fill in your Supabase + API values

npm run dev
```

Visit `http://localhost:3000`.

### Production Build (locally)

```bash
npm run build
npm run start
```

---

## Project Structure

```
app/
├── page.tsx                  # Landing page (hero, features, live demo, pricing)
├── layout.tsx                # Root layout + metadata
├── auth/
│   ├── login/page.tsx
│   └── signup/page.tsx
├── dashboard/
│   └── page.tsx              # API keys, usage stats, live tester, quickstart
└── lib/
    ├── supabase.ts           # Auth + database helpers
    └── api.ts                # FraudShield API client
supabase_schema.sql           # Full DB schema — run once in Supabase SQL Editor
styles/globals.css            # Dark theme, shared component classes
```

---

## Environment Variables

See `.env.example` for the full template.

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | yes | From Supabase project settings → API |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | yes | Public anon key — safe to expose client-side (protected by Row Level Security) |
| `NEXT_PUBLIC_API_URL` | yes | Base URL of the deployed FraudShield API |
| `NEXT_PUBLIC_DEMO_API_KEY` | no | Optional key used only by the public landing page demonstration |

All variables are prefixed `NEXT_PUBLIC_` because they are read client-side; none of them are secret values that grant write access beyond what Row Level Security already permits.

---

## Database Setup (Supabase)

1. Create a project at [supabase.com](https://supabase.com).
2. Open **SQL Editor → New Query**, paste the entire contents of `supabase_schema.sql`, and run it.
3. This creates three tables — `user_profiles`, `api_keys`, `usage_logs` — each with **Row Level Security enabled**, so a user can only ever `SELECT`/`INSERT`/`UPDATE` rows where `user_id = auth.uid()`. A signup automatically creates a matching `user_profiles` row via a Postgres trigger (`handle_new_user()`).
4. Copy the **Project URL** and **anon public key** from Settings → API into your `.env.local` / Vercel environment variables.

---

## Testing, Build and Type Safety

```bash
npx tsc --noEmit    # strict TypeScript check — zero errors required
npx next lint        # ESLint (next/core-web-vitals) — zero warnings required
npm run build        # full production build — must complete cleanly
```

All three are enforced in CI on every push and pull request; a red run blocks merge. Current status: **zero TypeScript errors, zero lint warnings, all 5 routes build and statically prerender successfully.**

> During pre-deploy review, `npx tsc --noEmit` caught a genuine broken import path (`../lib/supabase` instead of `../../lib/supabase`) in both the login and signup pages — a bug that would have completely broken the two most critical user flows in production. This is exactly the class of error a type-check gate is designed to catch before it ever reaches a customer, and it's why `tsc --noEmit` runs on every CI build here rather than being treated as optional.

---

## Error Handling

- Every Supabase auth call (`signUp`, `signIn`, `signOut`) returns a typed `{ data, error }` pair; the UI renders the error message directly rather than silently failing.
- Every FraudShield API call in `app/lib/api.ts` checks `response.ok` and throws a descriptive `Error` on failure, which calling components catch and surface as an inline error banner — no unhandled promise rejections.
- The landing page's live demo has a graceful fallback: if the API is unreachable, it displays a clearly-labeled representative result rather than an unhandled network error, so a broken backend never breaks the marketing page.
- The dashboard checks for an authenticated session on mount and redirects to `/auth/login` if absent — no page ever renders in a broken "half-authenticated" state.

---

## Validation

- Signup requires a company/project name, a work email, and a password of at least 8 characters, checked client-side before the request is sent.
- All authentication and data-access rules are additionally enforced server-side by Supabase Row Level Security — client-side validation is a UX convenience, not the security boundary.
- The FraudShield API itself independently validates every field of every transaction sent from the "Test API" tab (see the [backend repo's validation documentation](https://github.com/fraudshield-ai/fraudshield-platform#input-validation)) — this frontend never assumes its own input is trustworthy once it leaves the browser.

---

## Security

| Control | Implementation |
|---|---|
| Authentication | Supabase Auth (email + password), session managed via `@supabase/supabase-js` |
| Authorization | Postgres Row Level Security on every table — a user's queries are scoped to `auth.uid()` at the database layer, not just in application code |
| API key display | Keys are masked by default in the dashboard (`Eye`/`EyeOff` toggle) and only copied to the clipboard on explicit user action |
| Transport | All Supabase and FraudShield API traffic is HTTPS-only |
| Secrets | No server-side secret keys are used or stored in this app — the Supabase anon key is safe to expose because RLS is the actual security boundary |
| Dependency vulnerabilities | `next` is pinned to the latest patched 14.2.x release (`14.2.35`), which resolves the critical cache-poisoning/DoS advisories present in earlier 14.2.0 builds. A small number of remaining advisories require a major-version jump to Next.js 16 (a breaking change); see [Known Limitations](#known-limitations) for the honest accounting |

---

## CI/CD

Every push and pull request runs (`.github/workflows/ci.yml`):

1. **Type check** — `tsc --noEmit`, zero errors required
2. **Lint** — `next lint`, zero warnings required
3. **Build** — full production build must complete
4. **Dependency audit** — `npm audit`, reported (not currently blocking, see Known Limitations)

---

## Deployment (Vercel)

```
1. Push the monorepo to GitHub (already done if you're reading this from the repo).
2. vercel.com → Add New → Project → import the repo.
3. In "Configure Project", set **Root Directory to `apps/web`** (the repo's
   root-level `vercel.json` also encodes this, so Vercel picks it up
   automatically in most cases — verify it in the project settings if not).
4. Set environment variables in the Vercel dashboard:
     NEXT_PUBLIC_SUPABASE_URL
     NEXT_PUBLIC_SUPABASE_ANON_KEY
     NEXT_PUBLIC_API_URL          (your deployed FraudShield API URL)
4. Deploy.
```

Vercel automatically redeploys on every push to `main`.

---

## Known Limitations

- **Remaining npm audit advisories require a major Next.js version bump.** After pinning to the latest patched `14.2.35` (which fixes the critical cache-poisoning/DoS issues present in `14.2.0`), `npm audit` still reports advisories that are only fully resolved in Next.js 16.x — a breaking major-version change. This app does not use the specific features most of those advisories concern (`next/image`, i18n middleware, React Server Component caching), so real-world exposure is low, but this is tracked as a deliberate, documented trade-off rather than a silently ignored warning. A dev-tooling-only `glob` advisory (via `eslint-config-next`) is lower risk still, since it requires direct CLI invocation this project's scripts never perform.
- **No end-to-end test suite yet.** Correctness is currently enforced via strict TypeScript, ESLint, and a full production build gate in CI, plus manual verification against a live backend. Playwright/Cypress e2e coverage is a natural next step once the user base grows past the beta stage.
- **Single Supabase project, no multi-region setup.** Fine for the current beta scale; would need revisiting well before high-volume production traffic.

---

## Contributing and Branching Workflow

```bash
git checkout -b feature/your-change
# ... make changes ...
npx tsc --noEmit
npx next lint
npm run build

git add -A
git commit -m "feat: description of your change"
git push origin feature/your-change
# open a Pull Request -- CI must pass before merge
```

---

## License

MIT License — see `LICENSE` for details.

---

## Author

**Shweta Mishra** — Python Developer and AI/ML Engineer

[LinkedIn](https://www.linkedin.com/in/shweta-mishra-ai) | [GitHub](https://github.com/Shweta-Mishra-ai)

# Architecture

This document explains **why** the repository is organized the way it is, so that future changes — new features, new services, new apps — follow the same pattern instead of drifting into an ad-hoc structure that needs to be reorganized later.

## The core rule

> **Every deployable unit lives under `apps/<name>/` and is fully self-contained: its own dependencies, its own tests, its own Dockerfile/build config, its own README.**

Today that's `apps/api` (FastAPI backend) and `apps/web` (Next.js frontend). If a mobile app, a separate admin tool, or a shared internal library is ever needed, it goes in `apps/mobile/`, `apps/admin/`, or `packages/shared/` — never mixed into an existing app's folder, and never requiring the existing apps to move.

This is the same pattern used by large-scale monorepos at companies like Vercel, Supabase, and Stripe's internal tooling: one repository, many independently-deployable apps, coordinated by path-filtered CI and per-app deploy configs.

## Why one repo instead of many

- **One source of truth.** A single commit history, a single set of issues/PRs, a single place to look for anything.
- **Atomic cross-app changes.** If an API response shape changes, the frontend change that consumes it can be reviewed and merged in the *same* pull request — no coordinating two repos, no risk of one being deployed without the other.
- **Still deploys independently.** Render only ever looks at `apps/api` (`render.yaml` → `rootDir: apps/api`). Vercel only ever looks at `apps/web` (`vercel.json`). Deploying a frontend change never redeploys the backend, and vice versa.

## Why this doesn't need to be "redistributed" as features grow

Three things are set **once** and never need to change when adding features:

1. **`render.yaml` → `rootDir: apps/api`** — every new endpoint, rule, or ML model added inside `apps/api/` is picked up automatically. Render never needs reconfiguring.
2. **`vercel.json` → builds from `apps/web`** — every new page or dashboard tab added inside `apps/web/` is picked up automatically. Vercel never needs reconfiguring.
3. **CI path filters** (`.github/workflows/api-ci.yml`, `web-ci.yml`) — each workflow triggers only when files under its own `apps/<name>/` change. Adding ten new features to the backend never triggers a frontend build, and vice versa. Neither workflow needs editing when new files are added inside the app it already watches.

In short: **the folder you add new code to determines everything automatically** — which CI runs, which service redeploys, which tests execute. There's no manual step where you have to update a path, a config, or a deployment target just because a feature was added.

## When you *would* need to touch this structure

Only three situations should ever require editing `render.yaml`, `vercel.json`, or the CI workflow files:

- Adding a genuinely new deployable app (e.g. `apps/mobile`) — add a new workflow file and, if it deploys, a new service block.
- Changing *how* an existing app builds (e.g. switching the API from Docker to a native buildpack) — a one-line change to the relevant deploy config, not a restructuring.
- Introducing shared code used by more than one app — goes in `packages/`, imported by whichever apps need it, with its own tests.

Routine feature work — new rules, new pages, new endpoints, new UI — never touches any of these files.

## Testing philosophy

Each app owns its own test suite and is responsible for its own correctness in isolation:

- `apps/api/tests/` — 173 tests (unit, integration, security) plus a dedicated regression suite (`tests/unit/test_critical_fixes.py`) that guards against every bug found during the pre-launch audit, so those specific mistakes can never silently reappear.
- `apps/web/` — TypeScript strict-mode compilation and ESLint are treated as the test suite's first line of defense (a broken import path was caught this way before it ever reached a user), backed by a full production build gate.

Both are wired into CI independently, so a broken backend can never block a frontend deploy and vice versa — but a pull request that touches both is still reviewed as one unit of work.

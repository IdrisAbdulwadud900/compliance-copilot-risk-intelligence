# Crypto Compliance Copilot

A real-time wallet risk intelligence engine with behavior fingerprinting, narrative detection, watchlist management, alert events, webhook delivery, and wallet clustering. Built for compliance teams monitoring blockchain activity.

## Features

✅ Risk scoring (0–100) with multi-signal analysis
✅ Behavior fingerprinting (10 patterns: sniper, wash-trader, bridge-hopper, insider, sanctions-linked, mixer-user, memecoin-cluster, etc.)
✅ Wallet narrative generation with confidence + recommended action (block/flag/monitor/watch)
✅ Wallet clustering with force-circle graph visualization
✅ Watchlist + auto-alerts on activity
✅ Alert acknowledgment + unread tracking
✅ Webhook delivery with HMAC-SHA256 signing
✅ Multi-chain support (Ethereum, Solana, Arbitrum, Base, BSC, Polygon)
✅ Multi-tenant isolation + role-based access (admin/analyst/viewer)
✅ JWT + API key auth
✅ Invite workflow + email-less onboarding
✅ Rate limiting + audit logging
✅ Tag management + CSV export
✅ Real-time severity pie chart + cluster visualization

## Quick Start

### Backend

```bash
cd backend
cp .env.example .env
python -m venv .venv  # if needed
source ../.venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python -m app.cli --env-file .env migrate
PYTHONPATH=. python -m uvicorn app.main:app --reload --port 8000
```

Local lifecycle scripts:

```bash
bash scripts/start_backend.sh
bash scripts/start_frontend.sh
bash scripts/status_local.sh
bash scripts/logs_local.sh backend
bash scripts/deploy_local.sh
bash scripts/stop_local.sh
bash scripts/reset_local_workspace.sh --dry-run
```

No login is seeded unless you explicitly set `COMPLIANCE_ADMIN_EMAIL`,
`COMPLIANCE_ADMIN_PASSWORD`, and `COMPLIANCE_ADMIN_TENANT`.

If the database has no users yet, the first email signup automatically becomes
the workspace admin. Later email signups keep their requested role.

To safely preview that first-run owner flow again on your local machine, run:

```bash
bash scripts/reset_local_workspace.sh --yes
```

That command backs up the current SQLite database under `backend/data/backups/`,
clears the active local DB, and restarts the stack so the next email signup
becomes the workspace owner/admin.

To restore the most recent saved local dataset afterward, run:

```bash
bash scripts/restore_local_workspace.sh --yes
```

You can also restore a specific backup file with `--backup path/to/file.db`.
The restore command backs up the current active DB first, then replaces it with
the chosen snapshot and restarts the stack.

For local preview only, you can opt into the seeded preview admin by also setting
`COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP=true`. The insecure preview password
`ChangeMe123!` is ignored unless that flag is enabled.

Preview OAuth and phone signup methods are also opt-in. Set
`COMPLIANCE_ENABLE_PREVIEW_AUTH_METHODS=true` on the backend and
`NEXT_PUBLIC_ENABLE_PREVIEW_AUTH=true` on the frontend only when you explicitly
want those non-production preview flows visible for demos.

### Frontend

```bash
cd app
npm install
npm run dev
# Visit http://localhost:3000
```

## Architecture

### Backend (FastAPI + modular routers)

**Core Modules:**
- `app/risk_engine.py` — Wallet risk scoring (0–100) with chain multipliers
- `app/intelligence.py` — Behavior fingerprinting + narrative generation + confidence capping
- `app/cluster.py` — Deterministic related-wallet graph (up to 8 nodes)
- `app/webhooks.py` — Fire-and-forget HMAC-SHA256 webhook delivery
- `app/db.py` — Multi-tenant SQLite persistence layer with production guardrails and future DB portability hooks
- `app/migrations.py` — Versioned SQLite schema migrations applied automatically at startup
- `app/auth.py` — JWT + API key authentication
- `app/routers/` — domain routers for auth, intelligence, alerts, incidents, cases, watchlist, team, and webhooks
- `app/main.py` — app assembly, health/readiness, analytics, and cluster endpoint

### Frontend (Next.js 16 + React 19)

**Pages:**
- `/` — Main dashboard (intelligence, watchlist, alerts, webhooks, team)
- `/invite?token=...` — Invite acceptance

---

## API Endpoints

### Public

```bash
GET /health
GET /ready
```

### Protected (JWT or API Key)

**Intelligence:**
- `POST /wallets/intelligence` → fingerprints + narrative + recommended action
- `GET /wallets/{address}/cluster?chain=ethereum` → graph nodes + edges

**Watchlist:**
- `GET /watchlist`, `POST /watchlist`, `DELETE /watchlist/{id}`

**Alerts:**
- `GET /alert-events?limit=50&unacked_only=false`, `POST /alert-events/{id}/ack`

**Webhooks (Admin):**
- `GET /webhooks`, `POST /webhooks`, `DELETE /webhooks/{id}`

**Auth:**
- `POST /auth/login`, `POST /auth/accept-invite`, `POST /auth/change-password`

**Team (Admin):**
- `POST /users`, `GET /users`, `POST /users/invite`, `GET /users/invites`, `DELETE /users/invites/{token}`

**Other:**
- `GET /dashboard`, `GET /audit-logs`

---

## Risk Scoring

**Score Factors:**
- Sanctions exposure (0–40)
- Mixer usage (0–30)
- Bridge hops (0–20)
- Chain multiplier (±10, BSC/Polygon higher)
- Behavioral patterns (±10)

**Actions:**
| Score | Action  |
|-------|---------|
| ≥85   | Block   |
| ≥65   | Flag    |
| ≥40   | Monitor |
| <40   | Watch   |

---

## Testing

```bash
cd backend
python -m pytest tests/ -v
```

`138` backend tests passing covering auth, multi-tenancy, intelligence routes, RBAC, watchlist, alerts, incidents, cases, webhooks, and cluster flows.

## Database Migrations

- Backend startup now runs internal versioned migrations before seeding any bootstrap admin.
- Migration state is tracked in the `schema_migrations` table.
- Existing SQLite databases are upgraded in place; fresh databases receive the full schema automatically.
- Current production posture is still SQLite-first, but schema changes are now tracked explicitly instead of living only in `init_db`.
- `/health` and `/ready` now expose migration state so deploy checks can detect schema drift.

Manual commands:

```bash
cd backend
PYTHONPATH=. python -m app.cli --env-file .env status
PYTHONPATH=. python -m app.cli --env-file .env migrate
PYTHONPATH=. python -m app.cli --env-file .env health --url http://127.0.0.1:8000/health
PYTHONPATH=. python -m app.cli --env-file .env preflight --url http://127.0.0.1:8000/health
```

---

## Tech Stack

- **Backend:** Python 3.9.6, FastAPI 0.104, SQLite (current), Pydantic v2, python-jose
- **Frontend:** Next.js 16.2.0, React 19, TypeScript 5, Tailwind CSS 4, Recharts
- **Testing:** pytest + FastAPI TestClient

---

## Deployment Notes

Use environment variables for secrets:
- `COMPLIANCE_DB_PATH` → active SQLite file path
- `COMPLIANCE_DATABASE_URL` → optional `sqlite:///...` or `postgresql://...` runtime target
- `COMPLIANCE_JWT_SECRET` → JWT signing key
- `COMPLIANCE_WEBHOOK_SECRET` → Webhook HMAC secret
- `COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP` → enable preview/demo bootstrap only for local testing
- `COMPLIANCE_ENABLE_PREVIEW_AUTH_METHODS` → enable preview OAuth/phone signup endpoints only for demos
- `COMPLIANCE_ADMIN_EMAIL`, `COMPLIANCE_ADMIN_PASSWORD`, `COMPLIANCE_ADMIN_TENANT`, `COMPLIANCE_ADMIN_ROLE`

For production:
- PostgreSQL runtime foundations are now present, but should still be validated in your target environment before cutover
- Enable HTTPS + CORS restrictions
- Store secrets in Vault/AWS Secrets Manager
- Keep `COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP=false`
- Keep `COMPLIANCE_ENABLE_PREVIEW_AUTH_METHODS=false`
- Do not use the preview password `ChangeMe123!`
- Monitor webhook delivery logs
- Run in CI/CD pipeline
- `GET /users/invites` (admin)
- `DELETE /users/invites/{token}` (admin)
- `GET /audit-logs` (admin)

All endpoints except `GET /health` and `GET /ready` require authentication:
- `Authorization: Bearer <token>` from `/auth/login`, or
- `x-api-key` header as fallback.

## Login (JWT)

Create an admin user by setting bootstrap env vars before first startup, then
login from the dashboard UI header.

Preview OAuth/phone signup buttons stay hidden unless `NEXT_PUBLIC_ENABLE_PREVIEW_AUTH=true` is set in the frontend environment.

## Invite onboarding

Admins can issue invites from the team panel or via `POST /users/invite`.
Invited users complete onboarding with `POST /auth/accept-invite` using invite token and password.

## Tenant auth config

Set backend `COMPLIANCE_API_KEYS` as comma-separated `api_key:tenant_id:role` pairs.

Example:

```env
COMPLIANCE_API_KEYS="acme-analyst-key:acme-finance:analyst"
```

Set frontend key in `.env.local`:

```env
NEXT_PUBLIC_API_KEY=
```

## Rate limiting (auth hardening)

Backend supports basic IP-based rate limiting for sensitive auth endpoints.

```env
COMPLIANCE_RATE_LIMIT_ENABLED=true
COMPLIANCE_RATE_LIMIT_WINDOW_SECONDS=60
COMPLIANCE_RATE_LIMIT_AUTH_MAX_REQUESTS=10
COMPLIANCE_RATE_LIMIT_INVITE_STATUS_MAX_REQUESTS=30
```

## Tests

```bash
cd "/Users/mac/Downloads/operation make money/backend"
"/Users/mac/Downloads/operation make money/.venv/bin/python" -m pytest -q
```

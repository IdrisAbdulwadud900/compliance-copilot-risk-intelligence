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
PYTHONPATH=. python -m uvicorn app.main:app --reload --port 8000
```

**Default Login:** `founder@demo.local` / `ChangeMe123!`

### Frontend

```bash
cd app
npm install
npm run dev
# Visit http://localhost:3000
```

## Architecture

### Backend (FastAPI + SQLite)

**Core Modules:**
- `app/risk_engine.py` — Wallet risk scoring (0–100) with chain multipliers
- `app/intelligence.py` — Behavior fingerprinting + narrative generation + confidence capping
- `app/cluster.py` — Deterministic related-wallet graph (up to 8 nodes)
- `app/webhooks.py` — Fire-and-forget HMAC-SHA256 webhook delivery
- `app/db.py` — Multi-tenant SQLite with 9 tables + CRUD ops
- `app/auth.py` — JWT + API key authentication
- `app/main.py` — 30+ FastAPI routes with RBAC

### Frontend (Next.js 16 + React 19)

**Pages:**
- `/` — Main dashboard (intelligence, watchlist, alerts, webhooks, team)
- `/invite?token=...` — Invite acceptance

---

## API Endpoints

### Public (Demo Key)

```bash
GET /health
GET /analyses?limit=20
POST /wallets/explain
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

**13 tests passing** covering auth, multi-tenancy, intelligence routes, RBAC, watchlist, alerts, webhooks, and cluster.

---

## Tech Stack

- **Backend:** Python 3.9.6, FastAPI 0.104, SQLite, Pydantic v2, python-jose
- **Frontend:** Next.js 16.2.0, React 19, TypeScript 5, Tailwind CSS 4, Recharts
- **Testing:** pytest + FastAPI TestClient

---

## Deployment Notes

Use environment variables for secrets:
- `COMPLIANCE_DB_PATH` → SQLite/PostgreSQL path
- `COMPLIANCE_JWT_SECRET` → JWT signing key
- `COMPLIANCE_WEBHOOK_SECRET` → Webhook HMAC secret
- `COMPLIANCE_ADMIN_EMAIL`, `COMPLIANCE_ADMIN_PASSWORD`, `COMPLIANCE_ADMIN_TENANT`, `COMPLIANCE_ADMIN_ROLE`

For production:
- Switch to PostgreSQL
- Enable HTTPS + CORS restrictions
- Store secrets in Vault/AWS Secrets Manager
- Monitor webhook delivery logs
- Run in CI/CD pipeline
- `GET /users/invites` (admin)
- `DELETE /users/invites/{token}` (admin)
- `GET /audit-logs` (admin)

All endpoints except `GET /health` require authentication:
- `Authorization: Bearer <token>` from `/auth/login`, or
- `x-api-key` header as fallback.

## Login (JWT)

Default seeded credentials (from `backend/.env.example`):

```text
email: founder@demo.local
password: ChangeMe123!
```

You can sign in from the dashboard UI header.

## Invite onboarding

Admins can issue invites from the team panel or via `POST /users/invite`.
Invited users complete onboarding with `POST /auth/accept-invite` using invite token and password.

## Tenant auth config

Set backend `COMPLIANCE_API_KEYS` as comma-separated `api_key:tenant_id` pairs.

Example:

```env
COMPLIANCE_API_KEYS="demo-key:demo-tenant,acme-key:acme-finance"
```

Set frontend key in `.env.local`:

```env
NEXT_PUBLIC_API_KEY=demo-key
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

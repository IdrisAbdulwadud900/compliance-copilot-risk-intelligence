# Compliance Copilot

Compliance Copilot is a prototype crypto compliance workspace for teams that need to investigate wallets, explain risk decisions, monitor watched addresses, and move suspicious activity into incidents and cases.

It is designed for:
- exchanges and OTC desks
- payment and treasury operations teams
- compliance analysts and AML investigators
- founder-led pilots where you want one place to score wallets, review clusters, and document decisions

## What the product does

Compliance Copilot combines wallet intelligence with analyst workflow:

- wallet enrichment and scoring
- behavior fingerprinting and narrative generation
- wallet cluster visualization
- watchlists and alerts
- incidents and case management
- team access, invites, audit logs, and exports

## What is live today vs. prototype today

### Strongest capability today
- **Ethereum live enrichment and clustering**
- end-to-end analyst workflow from wallet → alert → incident → case
- multi-user auth, invite onboarding, audit trail, and admin controls

### Prototype / partial capability today
- **Base, Arbitrum, BSC, Polygon, and Solana** currently support analyst-driven/manual intelligence workflows better than fully live chain connectors
- production backend is still using **ephemeral SQLite on Vercel** until `COMPLIANCE_DATABASE_URL` is set to managed Postgres

That means the product is good for demos, pilots, and workflow validation right now, but not yet at full enterprise reliability.

## Why someone would test it

This repo is best tested by people who can answer questions like:
- Would this save an analyst time during wallet review?
- Is the narrative and recommended action credible enough to be useful?
- Does the cluster view help explain risk faster than raw block explorer work?
- Is the watchlist / alert / case workflow good enough for a real team?

Good pilot testers include:
- compliance or AML analysts at crypto companies
- operations leads at OTC desks or exchanges
- crypto risk consultants
- founders and operators who manually review counterparties today

## Core capabilities

- risk scoring from 0–100
- wallet narratives and behavior fingerprints
- Ethereum live enrichment and cluster generation
- multi-chain analyst workflow coverage
- watchlist-triggered alerts
- alert acknowledgement and resolution
- incidents and cases
- webhook delivery with HMAC signing
- JWT auth, role-based access, invites, and audit logs
- CSV export and tagging

## Product status summary

### Useful now for
- demos
- founder-led pilots
- internal analyst workflow validation
- showing a real crypto compliance operations desk experience

### Not fully solved yet
- durable production persistence until Postgres is configured
- equal live-data depth across all supported chains
- enterprise-grade reliability and SLA posture

## Repository guide

- [API.md](API.md) — endpoint reference
- [ARCHITECTURE.md](ARCHITECTURE.md) — backend and frontend system design
- [DEPLOY.md](DEPLOY.md) — local and production deployment guide

## Quick start

### Prerequisites
- Python 3.9+
- Node.js 18+
- npm

### Backend

```bash
cd backend
cp .env.example .env
python -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python -m app.cli --env-file .env migrate
PYTHONPATH=. uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd app
npm install
npm run dev
```

Open:
- frontend: `http://localhost:3000`
- backend docs: `http://127.0.0.1:8000/docs`

## Local helper scripts

From the repo root:

```bash
bash scripts/start_backend.sh
bash scripts/start_frontend.sh
bash scripts/status_local.sh
bash scripts/logs_local.sh backend
bash scripts/deploy_local.sh
bash scripts/stop_local.sh
```

## Authentication and first-time setup

No default login is seeded unless you explicitly opt into preview bootstrap.

### Normal local / pilot behavior
- if the workspace has **no users**, the **first email signup becomes admin**
- later signups keep their requested role

### Optional preview-only bootstrap
Only for demos, you can set:

```env
COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP=true
COMPLIANCE_ADMIN_EMAIL=founder@demo.local
COMPLIANCE_ADMIN_PASSWORD=ChangeMe123!
COMPLIANCE_ADMIN_TENANT=demo-tenant
```

Do **not** use that flow for real deployments.

### Preview auth methods
OAuth/phone preview UI stays hidden unless you opt in with:

```env
COMPLIANCE_ENABLE_PREVIEW_AUTH_METHODS=true
NEXT_PUBLIC_ENABLE_PREVIEW_AUTH=true
```

## How to use the product

### 1. Create or sign into a workspace
- sign up with a work email if the workspace is empty
- or sign in with existing operator credentials

### 2. Investigate a wallet
- paste a wallet address
- choose the chain
- enrich / analyze it
- review score, fingerprints, narrative, and recommended action

### 3. Review relationships
- open the cluster graph
- inspect linked wallets and relationship edges
- use the narrative to summarize what the cluster implies

### 4. Escalate if needed
- add the wallet to a watchlist
- create or resolve alerts
- open an incident
- create a case and attach notes, entities, and evidence links

## Real-wallet testing

Two QA scripts are included:

### Live Ethereum workflow QA
```bash
source .venv/bin/activate
python scripts/real_wallet_qa.py
```

This validates:
- live enrichment
- intelligence scoring
- cluster generation
- watchlist / alert / incident / case flow

### Cross-chain QA
```bash
source .venv/bin/activate
python scripts/cross_chain_wallet_qa_tmp.py
```

This validates supported-chain workflow behavior across:
- Ethereum
- Base
- Arbitrum
- BSC
- Polygon
- Solana

Both scripts now auto-bootstrap a QA user if the local workspace is empty, or they can use:

```env
COMPLIANCE_QA_EMAIL=qa.operator@demo.local
COMPLIANCE_QA_PASSWORD=StrongPass123!
```

## Current real-wallet evidence

Recent QA runs showed:
- Vitalik wallet: low-signal / low-risk / root-only cluster behavior
- Binance hot wallet: strong live activity, large 24h volume, and meaningful cluster output
- USDC contract: graceful low-signal handling for a busy contract address
- watchlist → alert → incident → case workflow works end to end locally

## Testing

### Backend tests
```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```

### Frontend build validation
```bash
cd app
npm run build
```

## Deployment summary

### Frontend
- deployed on Vercel

### Backend
- deployed on Vercel
- current live health/readiness explicitly report persistence state

### Important production note
If `/ready` returns:
- `status: degraded`
- `database.persistence: ephemeral`
- `recommended_action` asking for `COMPLIANCE_DATABASE_URL`

then production is **not yet durable** and user/account data may be lost across deploys.

## Environment variables that matter most

### Backend
- `COMPLIANCE_JWT_SECRET`
- `COMPLIANCE_WEBHOOK_SECRET`
- `COMPLIANCE_ALLOWED_ORIGINS`
- `COMPLIANCE_DATABASE_URL`
- `COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP`
- `COMPLIANCE_ENABLE_PREVIEW_AUTH_METHODS`

### Frontend
- `NEXT_PUBLIC_API_BASE`
- `NEXT_PUBLIC_ENABLE_PREVIEW_AUTH`
- `NEXT_PUBLIC_API_KEY`

## Honest limitations

- production persistence still needs Postgres
- non-Ethereum chains are not yet equally live/data-rich
- pricing above small-pilot level is hard to justify until persistence and broader chain depth are improved

## If you want outside testers

The fastest path is to recruit **5–10 pilot users** who match your ideal buyer:
- 2 compliance analysts
- 2 exchange / OTC ops people
- 1–2 crypto risk consultants
- 1 founder or head of compliance at a small crypto firm

Ask them to do 3 tasks:
- assess one known low-risk wallet
- assess one high-activity / exchange wallet
- escalate one wallet through watchlist, alert, incident, and case flow

Then ask:
- what did you trust?
- what felt fake?
- what saved time?
- what was missing before this could become a paid tool?

## Prototype pricing reality

Right now this repo is strongest as:
- an internal tool
- a pilot
- a premium prototype

It is **not yet a strong self-serve $1k/month SaaS** until durable storage and broader live chain coverage are finished.

# Architecture & Implementation Guide

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js 16)                      │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Dashboard  │ Watchlist │ Alerts │ Webhooks │ Team    │    │
│  │  Cluster Graph │ Intelligence Panel │ Invite Form       │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  HTTP/JSON ← JWT / API Key Auth                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                 Backend (FastAPI 0.104)                       │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ Routes: /auth /wallets /watchlist /alerts /webhooks │     │
│  │         /users /audit-logs /dashboard               │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                               │
│  ┌────────────────────────────────────────────────────┐      │
│  │  Business Logic                                      │      │
│  │  ┌──────────────┐   ┌──────────────┐               │      │
│  │  │ risk_engine  │   │intelligence  │               │      │
│  │  │ (scoring)    │   │(fingerprint) │               │      │
│  │  └──────────────┘   └──────────────┘               │      │
│  │  ┌──────────────┐   ┌──────────────┐               │      │
│  │  │ cluster.py   │   │ webhooks.py  │               │      │
│  │  │(graph build) │   │(fire+verify) │               │      │
│  │  └──────────────┘   └──────────────┘               │      │
│  └────────────────────────────────────────────────────┘      │
│                                                               │
│  ┌────────────────────────────────────────────────────┐      │
│  │  Data Access (SQLite)                                │      │
│  │  ┌──────────────────────────────────────────────┐  │      │
│  │  │ users │ analyses │ watchlist │ alerts │hooks│  │      │
│  │  └──────────────────────────────────────────────┘  │      │
│  └────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## Module Structure

### `app/risk_engine.py`

**Purpose:** Score wallets 0–100 based on on-chain signals.

**Key Function:** `score_wallet(wallet: WalletInput) -> WalletScore`

**Factors:**
1. **Sanctions Exposure** (0–40 pts)
   - Directly sanctioned address: +40
   - Adjacent to sanctioned: +20
   - Otherwise: +pts based on `sanctions_exposure_pct`

2. **Mixer Usage** (0–30 pts)
   - Direct mixer: +30
   - Mixer-adjacent: +15
   - Based on `mixer_exposure_pct`

3. **Bridge Activity** (0–20 pts)
   - Each bridge hop: +5 pts per hop (capped 20)

4. **Chain Multiplier** (±10 pts)
   - BSC/Polygon: +10 (higher enforcement risk)
   - Ethereum/Solana: 0 (regulatory clarity)
   - Arbitrum/Base: +5

5. **Behavioral Patterns** (±10 pts)
   - High txn_24h + low volume_24h = wash trading signal → +8
   - Low txn + high volume = whale move → +5
   - Otherwise: score variance ±5

**Output:**
```python
class WalletScore(BaseModel):
    address: str
    score: int  # 0–100
    risk_level: RiskLevel  # low/medium/high/critical
    reason: str  # Human-readable explanation
```

---

### `app/intelligence.py`

**Purpose:** Generate behavior fingerprints and narrative with confidence + recommended action.

**Key Functions:**

1. `fingerprint_wallet(wallet, scored) -> List[BehaviorFingerprint]`
   - Detects 10 behavioral patterns
   - Each returns: label, display name, description, confidence (0–100)

2. `detect_narrative(wallet, scored, fingerprints) -> WalletNarrative`
   - Combines fingerprints into a story
   - Calculates recommended action:
     - Score ≥85 OR sanctions_linked → **block**
     - Score ≥65 OR mixer/bridge high → **flag**
     - Score ≥40 OR wash/insider → **monitor**
     - Otherwise → **watch**
   - Caps confidence at 97% to acknowledge uncertainty
   - Returns business-context copy

**Fingerprint Patterns:**

| Label | Trigger | Points |
|-------|---------|--------|
| `sniper` | txn_24h >500 + volume low | 75 conf |
| `wash_trader` | High txn + low volume + same counterparty signals | 65 conf |
| `bridge_hopper` | bridge_hops ≥4 | 80 conf |
| `insider` | Accumulation pattern before news | 50 conf |
| `sanctions_linked` | Direct sanctions match | 95 conf |
| `sanctions_adjacent` | Indirect sanctions exposure | 70 conf |
| `mixer_user` | Direct mixer interaction | 90 conf |
| `mixer_adjacent` | Funding from mixer addresses | 75 conf |
| `memecoin_cluster` | Coordinated early buys | 60 conf |
| `whale_move` | Single large transaction | 55 conf |

---

### `app/cluster.py`

**Purpose:** Build a deterministic related-wallet graph from a root wallet.

**Key Function:** `build_cluster(root_wallet, root_score_int, max_nodes=8) -> WalletClusterResponse`

**Algorithm:**

1. **Root Node:** The input wallet
2. **Related Nodes:** Derived deterministically via SHA256/MD5 of root address
   - Ensures same cluster every time for same input
   - Number of related wallets scales with risk signal (2–8)
3. **Relations:** bridge_hop, co_funded, common_counterparty
   - Assigned from a weighted pool based on wallet signals
4. **Cross-Links:** Denser graph with 30% probability between non-root nodes
5. **Cluster Risk:** Maximum risk_level among all nodes

**Output:**
```python
class WalletClusterResponse(BaseModel):
    root_address: str
    nodes: List[ClusterNode]  # 1–8 nodes
    edges: List[ClusterEdge]  # Directed relations
    cluster_risk: RiskLevel
    narrative: str  # English summary of cluster
```

---

### `app/webhooks.py`

**Purpose:** Fire HMAC-signed HTTP webhooks for alerts.

**Key Function:** `fire_webhooks(webhooks, event_type, alert) -> None`

**Behavior:**
- Fire-and-forget (no retry logic; logs failures)
- HMAC-SHA256 signature in `X-Compliance-Signature` header
- Timeout: 10 seconds (configurable)
- Events: `alert.fired`, `wallet.flagged`, `watchlist.hit`

**Signature Calculation:**
```python
signature = hmac.new(
    WEBHOOK_SECRET.encode(),
    json.dumps(payload).encode(),
    hashlib.sha256
).hexdigest()
header_value = f"sha256={signature}"
```

---

### `app/db.py`

**Purpose:** Multi-tenant SQLite persistence.

**Tables:**

1. **users** — Team members (email, hashed password, role, tenant_id)
2. **tenants** — Isolated organizations
3. **analyses** — Wallet risk analyses (address, score, chain, tags)
4. **audit_logs** — Action trail (actor_email, action, target, timestamp)
5. **invites** — Pending team invites (token, email, status, expiry)
6. **watchlist** — Watched wallets (chain, address, label, created_by)
7. **alert_events** — Fired alerts (trigger, risk_level, acknowledged)
8. **webhooks** — Webhook configs (url, events, active)
9. **rate_limits** — Rate limit buckets (tenant:ip, count, reset_at)

**Key Functions:**
- `save_analysis`, `list_recent_analyses`
- `add_to_watchlist`, `is_on_watchlist`, `touch_watchlist_entry` (updates last_score)
- `save_alert_event`, `list_alert_events`, `acknowledge_alert`
- `save_webhook`, `list_webhooks`, `delete_webhook`
- `save_audit_log`, `list_audit_logs`
- Multi-tenant isolation: all queries filtered by `tenant_id`

---

### `app/auth.py`

**Purpose:** JWT + API key authentication.

**Functions:**

1. `get_current_principal(auth_header, api_key) -> tuple[tenant_id, role, email]`
   - Verifies JWT or API key
   - Returns tenant context + actor identity

2. `login_and_issue_token(email, password) -> tuple[token, email, tenant_id, role]`
   - Issues JWT valid for 24h (configurable)

3. `get_current_tenant(auth_header, api_key) -> str`
   - Extracts tenant_id from auth context

---

### `app/rate_limit.py`

**Purpose:** Per-tenant rate limiting.

**Function:** `enforce_rate_limit(action, key) -> None`

**Behavior:**
- Tracks requests per action/tenant+ip
- Limits: `login` (5/min), `intelligence` (20/min), `invite_status` (10/min)
- Resets every 60 seconds

---

### `app/ai_explainer.py`

**Purpose:** Generate plain-English alert explanations.

**Function:** `explain_alert(scored: WalletScore, wallet: WalletInput) -> str`

**Output:** Human-readable summary of why the score was assigned.

---

## Request Flow: Intelligence Endpoint

```
1. POST /wallets/intelligence
   ├─ User: founder@demo.local (admin)
   ├─ Body: { chain, address, txn_24h, ..., bridge_hops }
   │
2. Route Handler (main.py)
   ├─ get_current_principal() → (tenant_id="tenant-a", role="admin", email)
   ├─ enforce_rate_limit("intelligence", "tenant-a:127.0.0.1")
   ├─ score_wallet(wallet) → WalletScore { score: 37, risk_level: "low" }
   ├─ explain_alert(scored, wallet) → explanation string
   │
3. Intelligence Engine (intelligence.py)
   ├─ fingerprint_wallet(wallet, scored) → [BehaviorFingerprint, ...]
   ├─ detect_narrative(wallet, scored, fingerprints) → WalletNarrative
   │   ├─ recommended_action: "watch" (score < 40)
   │   ├─ confidence: 85 (capped at 97)
   │   └─ business_context: "Monitor activity..."
   │
4. Watchlist Check (db.py)
   ├─ is_on_watchlist(tenant_id, chain, address) → boolean
   ├─ If true AND score ≥ 40:
   │   ├─ touch_watchlist_entry() → update last_score
   │   ├─ save_alert_event(trigger="watchlist_activity") → AlertEvent
   │   ├─ fire_webhooks(hooks, "alert.fired", alert)
   │   └─ save_audit_log(action="analysis.intelligence", ...)
   │
5. Return to Client
   └─ WalletIntelligenceResponse {
        analysis_id: 7,
        score: 37,
        fingerprints: [...],
        narrative: {...}
      }
```

---

## Testing Strategy

**Unit Tests:**
- `test_auth.py` — JWT issuance + tenant resolution
- `test_risk_engine.py` — Score calculation with chain multipliers
- `test_db.py` — Multi-tenant isolation + CRUD ops

**Integration Tests:**
- `test_invite_password_flow.py` — Full invite → accept → password-change
- `test_intelligence_endpoints.py` — Intelligence + watchlist + alerts + webhooks + cluster
- `test_rate_limit.py` — Rate limit enforcement

**Coverage:**
- Role-based access control (admin/analyst/viewer blocking)
- Multi-tenant data isolation
- Watchlist trigger workflows
- Alert acknowledgment
- Webhook delivery

---

## Deployment Checklist

- [ ] Environment variables configured (secrets)
- [ ] Database migration (SQLite → PostgreSQL if scaling)
- [ ] SSL/TLS enabled for frontend + backend
- [ ] CORS configured for frontend origin
- [ ] Rate limits tuned for expected traffic
- [ ] Webhook timeout + retry policies
- [ ] Monitoring + logging configured
- [ ] Backup strategy for database
- [ ] Audit logs exported periodically
- [ ] Tests passing in CI/CD
- [ ] Frontend assets cached (CDN)
- [ ] Backend auto-scaling configured

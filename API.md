# API Reference

## Authentication

All protected endpoints require either:
1. JWT token in `Authorization: Bearer <token>` header, or
2. API key in `x-api-key: demo-key` header

### Login (Public)

```http
POST /auth/login
Content-Type: application/json

{
  "email": "founder@demo.local",
  "password": "ChangeMe123!"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "tenant_id": "tenant-a",
  "email": "founder@demo.local",
  "role": "admin"
}
```

---

## Wallet Intelligence

### Analyze Wallet (Admin/Analyst)

```http
POST /wallets/intelligence
Authorization: Bearer <token>
Content-Type: application/json

{
  "chain": "bsc",
  "address": "0xAABBCCDD11223344",
  "txn_24h": 200,
  "volume_24h_usd": 450000,
  "sanctions_exposure_pct": 8,
  "mixer_exposure_pct": 14,
  "bridge_hops": 4
}
```

**Response:**
```json
{
  "analysis_id": 42,
  "chain": "bsc",
  "address": "0xAABBCCDD11223344",
  "score": 62,
  "risk_level": "high",
  "explanation": "High risk: wallet scored 62/100 due to material sanctions exposure...",
  "fingerprints": [
    {
      "label": "mixer_user",
      "display": "Mixer User",
      "description": "Direct interaction with privacy-mixing services",
      "confidence": 85
    },
    {
      "label": "bridge_hopper",
      "display": "Bridge Hopper",
      "description": "Multi-chain bridge activity detected",
      "confidence": 72
    }
  ],
  "narrative": {
    "summary": "Wallet exhibits mixer usage and bridge-hopping patterns with elevated sanctions risk.",
    "business_context": "Recommend flagging for manual review and blocking further transactions until cleared.",
    "recommended_action": "flag",
    "recommended_action_label": "Flag for Review",
    "confidence": 87,
    "fingerprint_labels": ["mixer_user", "bridge_hopper", "sanctions_adjacent"]
  }
}
```

### Get Wallet Cluster (Admin/Analyst)

```http
GET /wallets/0xAABBCCDD11223344/cluster?chain=bsc
Authorization: Bearer <token>
```

**Response:**
```json
{
  "root_address": "0xAABBCCDD11223344",
  "nodes": [
    {
      "address": "0xAABBCCDD11223344",
      "chain": "bsc",
      "score": 62,
      "risk_level": "high",
      "fingerprints": ["mixer_user", "bridge_hopper"],
      "is_root": true
    },
    {
      "address": "0xDEADBEEFCAFE1234",
      "chain": "arbitrum",
      "score": 51,
      "risk_level": "medium",
      "fingerprints": ["co_funded", "wash_trader"],
      "is_root": false
    }
  ],
  "edges": [
    {
      "source": "0xAABBCCDD11223344",
      "target": "0xDEADBEEFCAFE1234",
      "relation": "bridge_hop",
      "strength": 0.85
    }
  ],
  "cluster_risk": "high",
  "narrative": "Cluster of 2 wallets identified across 2 chains. Multiple bridge-hop links detected between cluster members..."
}
```

---

## Watchlist

### Get Watchlist

```http
GET /watchlist
Authorization: Bearer <token>
```

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "tenant_id": "tenant-a",
      "chain": "ethereum",
      "address": "0xSUSPECT123",
      "label": "Known mixer operator",
      "created_at": "2026-03-21T10:00:00Z",
      "created_by": "founder@demo.local",
      "last_seen_at": "2026-03-21T22:15:00Z",
      "last_score": 78,
      "alert_on_activity": true
    }
  ]
}
```

### Add to Watchlist

```http
POST /watchlist
Authorization: Bearer <token>
Content-Type: application/json

{
  "chain": "ethereum",
  "address": "0xSUSPECT123",
  "label": "Known mixer operator",
  "alert_on_activity": true
}
```

### Remove from Watchlist

```http
DELETE /watchlist/1
Authorization: Bearer <token>
```

---

## Alert Events

### Get Alerts

```http
GET /alert-events?limit=50&unacked_only=false
Authorization: Bearer <token>
```

**Response:**
```json
{
  "items": [
    {
      "id": 42,
      "tenant_id": "tenant-a",
      "created_at": "2026-03-21T22:30:00Z",
      "trigger": "watchlist_activity",
      "chain": "ethereum",
      "address": "0xSUSPECT123",
      "score": 84,
      "risk_level": "critical",
      "title": "Watchlist hit: 0xSUSPECT123",
      "body": "Score 84 (critical). Wallet exhibits mixer usage and sanctions exposure. Recommended: block",
      "acknowledged": false
    }
  ],
  "unread_count": 3
}
```

### Acknowledge Alert

```http
POST /alert-events/42/ack
Authorization: Bearer <token>
```

---

## Webhooks (Admin Only)

### List Webhooks

```http
GET /webhooks
Authorization: Bearer <admin-token>
```

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "tenant_id": "tenant-a",
      "url": "https://your-server.com/compliance-webhook",
      "events": ["alert.fired", "wallet.flagged", "watchlist.hit"],
      "created_at": "2026-03-21T10:00:00Z",
      "active": true
    }
  ]
}
```

### Create Webhook

```http
POST /webhooks
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "url": "https://your-server.com/compliance-webhook",
  "events": ["alert.fired", "wallet.flagged", "watchlist.hit"]
}
```

### Delete Webhook

```http
DELETE /webhooks/1
Authorization: Bearer <admin-token>
```

---

## Webhook Delivery

Webhooks are sent as signed POST requests:

```http
POST https://your-server.com/compliance-webhook
X-Compliance-Signature: sha256=<hex_signature>
Content-Type: application/json

{
  "event_type": "alert.fired",
  "timestamp": "2026-03-21T22:30:00Z",
  "tenant_id": "tenant-a",
  "alert": {
    "id": 42,
    "chain": "ethereum",
    "address": "0xSUSPECT123",
    "score": 84,
    "risk_level": "critical",
    "title": "Critical score alert",
    "body": "Wallet scored 84/100...",
    "trigger": "score_threshold"
  }
}
```

**To verify the signature:**
```python
import hmac
import hashlib

secret = os.environ['COMPLIANCE_WEBHOOK_SECRET']
body = request.get_data()
signature = request.headers.get('X-Compliance-Signature', '')
expected = 'sha256=' + hmac.new(
    secret.encode(), 
    body, 
    hashlib.sha256
).hexdigest()

assert hmac.compare_digest(signature, expected)
```

---

## Team Management (Admin Only)

### Create Team User

```http
POST /users
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "email": "analyst@company.com",
  "password": "TempPass123!",
  "role": "analyst"
}
```

### Create Invite

```http
POST /users/invite
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "email": "analyst@company.com",
  "role": "analyst"
}
```

**Response:**
```json
{
  "token": "inv_abcd1234efgh5678",
  "email": "analyst@company.com",
  "role": "analyst",
  "expires_at": "2026-04-21T10:00:00Z"
}
```

### Accept Invite (Public)

```http
POST /auth/accept-invite
Content-Type: application/json

{
  "token": "inv_abcd1234efgh5678",
  "password": "NewPass123!"
}
```

---

## Other Endpoints

### Health

```http
GET /health
```

**Response:** `{"status": "ok"}`

### Dashboard

```http
GET /dashboard
Authorization: Bearer <token>
```

**Response:**
```json
{
  "total_wallets_monitored": 148,
  "alerts_today": 23,
  "critical_alerts_today": 2,
  "avg_risk_score": 46.8,
  "trend_7d": [12, 14, 11, 16, 19, 17, 23],
  "alerts": [...]
}
```

### Audit Logs

```http
GET /audit-logs?limit=25
Authorization: Bearer <admin-token>
```

---

## Error Codes

| Status | Meaning |
|--------|---------|
| 200    | Success |
| 400    | Bad request (validation error) |
| 401    | Unauthorized (missing/invalid auth) |
| 403    | Forbidden (insufficient role) |
| 404    | Not found |
| 409    | Conflict (duplicate entry) |
| 429    | Rate limited |
| 500    | Server error |

**Error response:**
```json
{
  "detail": "Insufficient role"
}
```

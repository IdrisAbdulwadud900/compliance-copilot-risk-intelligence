from pydantic import BaseModel, Field
from typing import List, Literal, Optional

RiskLevel = Literal["low", "medium", "high", "critical"]
UserRole = Literal["admin", "analyst", "viewer"]
InviteStatus = Literal["active", "used", "expired", "revoked"]
Blockchain = Literal["ethereum", "solana", "arbitrum", "base", "bsc", "polygon"]
RecommendedAction = Literal["block", "flag", "monitor", "watch"]
AlertTrigger = Literal["score_threshold", "watchlist_activity", "new_cluster_link", "manual"]
WebhookEvent = Literal["alert.fired", "wallet.flagged", "watchlist.hit"]


# ---------------------------------------------------------------------------
# Intelligence layer
# ---------------------------------------------------------------------------

class BehaviorFingerprint(BaseModel):
    label: str
    display: str
    description: str
    confidence: int  # 0-100


class WalletNarrative(BaseModel):
    summary: str
    business_context: str
    recommended_action: RecommendedAction
    recommended_action_label: str
    confidence: int
    fingerprint_labels: List[str] = Field(default_factory=list)


class WalletIntelligenceResponse(BaseModel):
    analysis_id: int
    chain: Blockchain = "ethereum"
    address: str
    score: int
    risk_level: RiskLevel
    explanation: str
    fingerprints: List[BehaviorFingerprint] = Field(default_factory=list)
    narrative: WalletNarrative


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

class WatchlistEntry(BaseModel):
    id: int
    tenant_id: str
    chain: Blockchain
    address: str
    label: str
    created_at: str
    created_by: str
    last_seen_at: Optional[str] = None
    last_score: Optional[int] = None
    alert_on_activity: bool = True


class WatchlistAddRequest(BaseModel):
    chain: Blockchain
    address: str = Field(min_length=8)
    label: str = Field(min_length=1, max_length=80)
    alert_on_activity: bool = True


class WatchlistPayload(BaseModel):
    items: List[WatchlistEntry]


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class AlertEvent(BaseModel):
    id: int
    tenant_id: str
    created_at: str
    trigger: AlertTrigger
    chain: Blockchain
    address: str
    score: int
    risk_level: RiskLevel
    title: str
    body: str
    acknowledged: bool = False


class AlertEventPayload(BaseModel):
    items: List[AlertEvent]
    unread_count: int = 0


class AlertAckRequest(BaseModel):
    acknowledged: bool = True


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

class WebhookConfig(BaseModel):
    id: int
    tenant_id: str
    url: str
    events: List[WebhookEvent]
    created_at: str
    active: bool = True


class WebhookConfigRequest(BaseModel):
    url: str = Field(min_length=10)
    events: List[WebhookEvent] = Field(default_factory=lambda: ["alert.fired"])


class WebhookConfigPayload(BaseModel):
    items: List[WebhookConfig]


# ---------------------------------------------------------------------------
# Wallet cluster / graph
# ---------------------------------------------------------------------------

class ClusterNode(BaseModel):
    address: str
    chain: Blockchain
    score: int
    risk_level: RiskLevel
    fingerprints: List[str] = Field(default_factory=list)
    is_root: bool = False


class ClusterEdge(BaseModel):
    source: str
    target: str
    relation: str  # "bridge_hop", "co_funded", "common_counterparty"
    strength: float  # 0-1


class WalletClusterResponse(BaseModel):
    root_address: str
    nodes: List[ClusterNode]
    edges: List[ClusterEdge]
    cluster_risk: RiskLevel
    narrative: str


class WalletInput(BaseModel):
    chain: Blockchain = "ethereum"
    address: str = Field(min_length=8)
    txn_24h: int = Field(ge=0)
    volume_24h_usd: float = Field(ge=0)
    sanctions_exposure_pct: float = Field(ge=0, le=100)
    mixer_exposure_pct: float = Field(ge=0, le=100)
    bridge_hops: int = Field(ge=0)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5)
    password: str = Field(min_length=8)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    email: str
    role: UserRole


class WalletScore(BaseModel):
    address: str
    score: int
    risk_level: RiskLevel
    reason: str


class TagUpdateRequest(BaseModel):
    tags: List[str] = Field(default_factory=list, max_length=10)


class AnalysisEntry(BaseModel):
    id: int
    created_at: str
    chain: Blockchain = "ethereum"
    address: str
    score: int
    risk_level: RiskLevel
    explanation: str
    tags: List[str] = Field(default_factory=list)


class WalletExplainResponse(BaseModel):
    analysis_id: int
    chain: Blockchain = "ethereum"
    address: str
    score: int
    risk_level: RiskLevel
    explanation: str


class Alert(BaseModel):
    id: str
    timestamp: str
    chain: Blockchain = "ethereum"
    title: str
    severity: RiskLevel
    score: int
    wallet: str
    amount_usd: float
    summary: str


class DashboardPayload(BaseModel):
    total_wallets_monitored: int
    alerts_today: int
    critical_alerts_today: int
    avg_risk_score: float
    trend_7d: List[int]
    alerts: List[Alert]


class AnalysisHistoryPayload(BaseModel):
    items: List[AnalysisEntry]


class AuditEntry(BaseModel):
    id: int
    created_at: str
    actor_email: str
    action: str
    target: str
    details: str


class AuditHistoryPayload(BaseModel):
    items: List[AuditEntry]


class TeamUser(BaseModel):
    id: int
    email: str
    tenant_id: str
    role: UserRole
    created_at: str


class TeamUserCreateRequest(BaseModel):
    email: str = Field(min_length=5)
    password: str = Field(min_length=8)
    role: UserRole


class TeamUserListPayload(BaseModel):
    items: List[TeamUser]


class InviteCreateRequest(BaseModel):
    email: str = Field(min_length=5)
    role: UserRole


class InviteResponse(BaseModel):
    token: str
    email: str
    role: UserRole
    expires_at: str


class InviteEntry(BaseModel):
    token: str
    email: str
    tenant_id: str
    role: UserRole
    created_at: str
    expires_at: str
    used_at: Optional[str] = None
    revoked_at: Optional[str] = None
    status: InviteStatus


class InviteListPayload(BaseModel):
    items: List[InviteEntry]


class InviteRevokeResponse(BaseModel):
    token: str
    revoked: bool


class InvitePublicStatusResponse(BaseModel):
    token: str
    status: InviteStatus
    email: str = ""
    role: UserRole = "viewer"
    expires_at: str = ""


class AcceptInviteRequest(BaseModel):
    token: str = Field(min_length=10)
    password: str = Field(min_length=8)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8)

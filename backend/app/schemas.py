import re
from pydantic import AnyHttpUrl, BaseModel, Field, model_validator
from typing import List, Literal, Optional

# EVM: canonical 20-byte address or a short safe synthetic identifier used by
# manual/test workflows that still starts with 0x and contains only alphanumerics.
_EVM_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_EVM_SYMBOLIC_RE = re.compile(r"^0x[0-9A-Za-z]{6,64}$")
# Solana: base58 alphabet, 32–44 chars
_SOLANA_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_EVM_CHAINS = frozenset({"ethereum", "arbitrum", "base", "bsc", "polygon"})


def _validate_wallet_address(chain: str, address: str) -> str:
    """Validate and sanitize a wallet address for the given chain."""
    # Strip surrounding whitespace
    address = address.strip()
    # Reject addresses with embedded whitespace or null bytes
    if any(c in address for c in (" ", "\t", "\n", "\r", "\x00")):
        raise ValueError("Wallet address must not contain whitespace or control characters")
    if chain in _EVM_CHAINS:
        if _EVM_RE.match(address):
            return address  # Preserve original casing for EVM addresses
        if _EVM_SYMBOLIC_RE.match(address):
            return address
        if not _EVM_RE.match(address):
            raise ValueError(
                f"Invalid EVM address for chain '{chain}': expected a canonical 0x + 40 hex address or a safe 0x-prefixed alphanumeric identifier"
            )
    if chain == "solana":
        if not _SOLANA_RE.match(address):
            raise ValueError(
                "Invalid Solana address: expected 32–44 base58 characters"
            )
        return address  # Solana addresses are case-sensitive
    # Unknown chain — pass through after basic sanitisation
    return address

RiskLevel = Literal["low", "medium", "high", "critical"]
UserRole = Literal["admin", "analyst", "viewer"]
InviteStatus = Literal["active", "used", "expired", "revoked"]
Blockchain = Literal["ethereum", "solana", "arbitrum", "base", "bsc", "polygon"]
RecommendedAction = Literal["block", "flag", "monitor", "watch"]
AlertTrigger = Literal["score_threshold", "watchlist_activity", "new_cluster_link", "manual"]
WebhookEvent = Literal["alert.fired", "wallet.flagged", "watchlist.hit"]
CaseStatus = Literal["open", "in_review", "escalated", "closed"]
CasePriority = Literal["low", "medium", "high", "critical"]
CaseEventType = Literal["case_created", "alert_linked", "analysis_linked", "note_added", "wallet_linked", "cluster_linked", "attachment_added", "status_changed"]
CaseEntityType = Literal["wallet", "cluster", "alert", "analysis", "transaction"]
AlertSeverity = Literal["info", "warning", "high", "critical"]
AlertType = Literal["score_threshold", "watchlist_hit", "volume_spike", "risk_change", "new_cluster_link", "manual"]
IncidentStatus = Literal["open", "investigating", "resolved", "closed"]
ClusterRelationType = Literal["shared_funding_source", "synchronized_activity", "common_counterparty", "cross_chain_bridge", "co_funded"]
ClusteringHeuristicType = Literal["shared_funding_source", "synchronized_activity", "common_counterparty", "cross_chain_link", "behavioral_similarity"]
ActivityBand = Literal["low", "moderate", "high"]


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

    @model_validator(mode="after")
    def validate_address(self) -> "WatchlistAddRequest":
        self.address = _validate_wallet_address(self.chain, self.address)
        return self


class WatchlistPayload(BaseModel):
    items: List[WatchlistEntry]


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class AlertEvent(BaseModel):
    """Legacy model – kept for backward compat. New code uses Alert."""
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


class Alert(BaseModel):
    """Full-featured alert with severity, type classification, and incident linking."""
    id: int
    tenant_id: str
    created_at: str
    trigger: AlertTrigger
    alert_type: AlertType
    severity: AlertSeverity
    chain: Blockchain
    address: str
    score: int
    prev_score: Optional[int] = None
    risk_level: RiskLevel
    title: str
    body: str
    acknowledged: bool = False
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    incident_id: Optional[int] = None


class AlertFeedPayload(BaseModel):
    """Response for both /alerts list and /alerts/feed polling."""
    items: List[Alert]
    unread_count: int = 0
    last_id: int = 0  # cursor: pass as since_id on next poll


class AlertEventPayload(BaseModel):
    items: List[Alert]
    unread_count: int = 0


class AlertAckRequest(BaseModel):
    acknowledged: bool = True


class CreateAlertRequest(BaseModel):
    alert_type: AlertType = "manual"
    severity: AlertSeverity = "warning"
    chain: Blockchain = "ethereum"
    address: str = Field(min_length=4, max_length=200)
    score: int = Field(default=0, ge=0, le=100)
    risk_level: RiskLevel = "medium"
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=3, max_length=2000)


class UpdateAlertRequest(BaseModel):
    resolved: Optional[bool] = None
    incident_id: Optional[int] = None


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
    url: AnyHttpUrl
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
    confidence: int = Field(default=0, ge=0, le=100)
    entity_likelihood: float = Field(default=0.0, ge=0.0, le=1.0)
    last_active_at: Optional[str] = None
    activity_band: ActivityBand = "low"
    is_root: bool = False


class ClusterHeuristicEvidence(BaseModel):
    heuristic: ClusteringHeuristicType
    confidence: int = Field(ge=0, le=100)
    weight: float = Field(ge=0.0, le=1.0)
    description: str
    related_addresses: List[str] = Field(default_factory=list)


class ClusterEdge(BaseModel):
    source: str
    target: str
    relation: ClusterRelationType
    strength: float  # 0-1
    confidence: int = Field(default=0, ge=0, le=100)
    shared_counterparties: int = Field(default=0, ge=0)
    same_entity_likelihood: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: List[ClusterHeuristicEvidence] = Field(default_factory=list)


class WalletClusterResponse(BaseModel):
    cluster_id: str
    root_address: str
    nodes: List[ClusterNode]
    edges: List[ClusterEdge]
    heuristics: List[ClusterHeuristicEvidence] = Field(default_factory=list)
    confidence: int = Field(ge=0, le=100)
    cluster_score: int = Field(ge=0, le=100)
    cluster_risk: RiskLevel
    cross_chain: bool = False
    last_updated_at: str
    refresh_suggested_after_sec: int = Field(default=60, ge=5)
    narrative: str


class WalletInput(BaseModel):
    chain: Blockchain = "ethereum"
    address: str = Field(min_length=8)
    txn_24h: int = Field(ge=0)
    volume_24h_usd: float = Field(ge=0)
    sanctions_exposure_pct: float = Field(ge=0, le=100)
    mixer_exposure_pct: float = Field(ge=0, le=100)
    bridge_hops: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_address(self) -> "WalletInput":
        self.address = _validate_wallet_address(self.chain, self.address)
        return self


class WalletEnrichmentResponse(WalletInput):
    source: str
    fetched_at: str
    asset_price_usd: float = Field(ge=0)
    balance_native: float = Field(ge=0)
    recent_tx_scanned: int = Field(ge=0)
    live_supported: bool = True
    notes: List[str] = Field(default_factory=list)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5)
    password: str = Field(min_length=8)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    email: str
    role: UserRole


class SignupEmailRequest(BaseModel):
    email: str = Field(min_length=5)
    password: str = Field(min_length=10)
    role: UserRole = "analyst"


class OAuthSignupRequest(BaseModel):
    provider: Literal["google", "apple"]
    email: str = Field(min_length=5)


class PhoneSignupStartRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=32)


class PhoneSignupVerifyRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=32)
    code: str = Field(min_length=4, max_length=8)


class SignupBootstrapResponse(BaseModel):
    status: Literal["ok"] = "ok"
    message: str


class SetupStatusResponse(BaseModel):
    status: Literal["ok"] = "ok"
    workspace_ready: bool
    user_count: int
    first_signup_becomes_admin: bool


class PhoneSignupStartResponse(BaseModel):
    status: Literal["ok"] = "ok"
    message: str
    code_hint: str


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


class DashboardAlert(BaseModel):
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
    alerts: List[DashboardAlert]


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


# ---------------------------------------------------------------------------
# Case management
# ---------------------------------------------------------------------------

class CaseSummary(BaseModel):
    id: int
    tenant_id: str
    title: str
    status: CaseStatus
    priority: CasePriority
    summary: str
    owner_email: str = ""
    source_type: str = "manual"
    source_ref: str = ""
    primary_chain: str = ""
    primary_address: str = ""
    risk_score: int = 0
    risk_level: RiskLevel = "low"
    tags: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    closed_at: Optional[str] = None


class CaseTimelineEvent(BaseModel):
    id: int
    case_id: int
    event_type: CaseEventType
    actor_email: str
    title: str
    body: str
    created_at: str


class CaseNote(BaseModel):
    id: int
    case_id: int
    note_type: Literal["observation", "hypothesis", "evidence", "decision"] = "observation"
    body: str
    tags: List[str] = Field(default_factory=list)
    author_email: str
    created_at: str


class CaseEntity(BaseModel):
    id: int
    case_id: int
    entity_type: CaseEntityType
    label: str
    chain: str = ""
    reference: str
    risk_score: Optional[int] = None
    risk_level: Optional[RiskLevel] = None
    created_at: str


class CaseAttachment(BaseModel):
    id: int
    case_id: int
    file_name: str
    file_url: str
    content_type: str = "link"
    uploaded_by: str
    created_at: str


class CaseDetail(CaseSummary):
    timeline: List[CaseTimelineEvent] = Field(default_factory=list)
    notes: List[CaseNote] = Field(default_factory=list)
    linked_entities: List[CaseEntity] = Field(default_factory=list)
    attachments: List[CaseAttachment] = Field(default_factory=list)
    activity: List[AuditEntry] = Field(default_factory=list)


class CaseListPayload(BaseModel):
    items: List[CaseSummary]


class CreateCaseRequest(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    summary: str = Field(min_length=3, max_length=500)
    priority: CasePriority = "medium"
    owner_email: str = ""
    source_type: str = "manual"
    source_ref: str = ""
    primary_chain: str = ""
    primary_address: str = ""
    risk_score: int = Field(default=0, ge=0, le=100)
    risk_level: RiskLevel = "low"
    tags: List[str] = Field(default_factory=list)


class UpdateCaseRequest(BaseModel):
    status: Optional[CaseStatus] = None
    priority: Optional[CasePriority] = None
    summary: Optional[str] = Field(default=None, min_length=3, max_length=500)
    owner_email: Optional[str] = None
    tags: Optional[List[str]] = None


class CreateCaseNoteRequest(BaseModel):
    note_type: Literal["observation", "hypothesis", "evidence", "decision"] = "observation"
    body: str = Field(min_length=2, max_length=4000)
    tags: List[str] = Field(default_factory=list)


class CreateCaseEntityRequest(BaseModel):
    entity_type: CaseEntityType
    label: str = Field(min_length=2, max_length=120)
    chain: str = ""
    reference: str = Field(min_length=2, max_length=240)
    risk_score: Optional[int] = Field(default=None, ge=0, le=100)
    risk_level: Optional[RiskLevel] = None


class CreateCaseAttachmentRequest(BaseModel):
    file_name: str = Field(min_length=2, max_length=180)
    file_url: AnyHttpUrl
    content_type: str = Field(default="link", min_length=2, max_length=80)


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
    password: str = Field(min_length=10)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=10)


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

class IncidentSummary(BaseModel):
    id: int
    tenant_id: str
    title: str
    description: str
    severity: AlertSeverity
    status: IncidentStatus
    alert_count: int
    created_at: str
    updated_at: str
    resolved_at: Optional[str] = None
    created_by: str


class IncidentDetail(IncidentSummary):
    alerts: List[Alert] = Field(default_factory=list)


class IncidentListPayload(BaseModel):
    items: List[IncidentSummary]


class CreateIncidentRequest(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(default="", max_length=1000)
    severity: AlertSeverity = "warning"
    alert_ids: List[int] = Field(default_factory=list)


class UpdateIncidentRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=160)
    description: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[IncidentStatus] = None
    severity: Optional[AlertSeverity] = None


class LinkAlertToIncidentRequest(BaseModel):
    alert_ids: List[int] = Field(min_length=1)

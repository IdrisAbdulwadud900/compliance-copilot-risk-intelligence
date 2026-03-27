export type RiskLevel = "low" | "medium" | "high" | "critical";
export type UserRole = "admin" | "analyst" | "viewer";
export type InviteStatus = "active" | "used" | "expired" | "revoked";
export type Blockchain = "ethereum" | "solana" | "arbitrum" | "base" | "bsc" | "polygon";
export type RecommendedAction = "block" | "flag" | "monitor" | "watch";
export type AlertTrigger = "score_threshold" | "watchlist_activity" | "new_cluster_link" | "manual";
export type WebhookEvent = "alert.fired" | "wallet.flagged" | "watchlist.hit";
export type AlertSeverity = "info" | "warning" | "high" | "critical";
export type AlertType = "score_threshold" | "watchlist_hit" | "volume_spike" | "risk_change" | "new_cluster_link" | "manual";
export type IncidentStatus = "open" | "investigating" | "resolved" | "closed";
export type CaseStatus = "open" | "in_review" | "escalated" | "closed";
export type CasePriority = "low" | "medium" | "high" | "critical";
export type CaseEventType =
  | "case_created"
  | "alert_linked"
  | "analysis_linked"
  | "note_added"
  | "wallet_linked"
  | "cluster_linked"
  | "attachment_added"
  | "status_changed";
export type CaseEntityType = "wallet" | "cluster" | "alert" | "analysis" | "transaction";

// Intelligence layer
export interface BehaviorFingerprint {
  label: string;
  display: string;
  description: string;
  confidence: number;
}

export interface WalletNarrative {
  summary: string;
  business_context: string;
  recommended_action: RecommendedAction;
  recommended_action_label: string;
  confidence: number;
  fingerprint_labels: string[];
}

export interface WalletIntelligenceResponse {
  analysis_id: number;
  chain: Blockchain;
  address: string;
  score: number;
  risk_level: RiskLevel;
  explanation: string;
  fingerprints: BehaviorFingerprint[];
  narrative: WalletNarrative;
}

// Watchlist
export interface WatchlistEntry {
  id: number;
  tenant_id: string;
  chain: Blockchain;
  address: string;
  label: string;
  created_at: string;
  created_by: string;
  last_seen_at: string | null;
  last_score: number | null;
  alert_on_activity: boolean;
}

export interface WatchlistAddRequest {
  chain: Blockchain;
  address: string;
  label: string;
  alert_on_activity: boolean;
}

export interface WatchlistPayload {
  items: WatchlistEntry[];
}

// Alert Events (v2 — includes all backend Alert model fields)
export interface AlertEvent {
  id: number;
  tenant_id: string;
  created_at: string;
  trigger: AlertTrigger;
  chain: Blockchain;
  address: string;
  score: number;
  risk_level: RiskLevel;
  title: string;
  body: string;
  acknowledged: boolean;
  acknowledged_at: string | null;
  resolved_at: string | null;
  alert_type: AlertType;
  severity: AlertSeverity;
  prev_score: number | null;
  incident_id: number | null;
}

/** Full Alert model — same shape as AlertEvent, exported as a clean alias. */
export type Alert = AlertEvent;

export interface AlertEventPayload {
  items: Alert[];
  unread_count: number;
}

export interface AlertFeedPayload {
  items: Alert[];
  unread_count: number;
  last_id: number;
}

export interface CreateAlertRequest {
  alert_type: AlertType;
  severity: AlertSeverity;
  chain: Blockchain;
  address: string;
  score: number;
  risk_level: RiskLevel;
  title: string;
  body: string;
  prev_score?: number;
}

export interface UpdateAlertRequest {
  resolved?: boolean;
  incident_id?: number | null;
}

export interface IncidentSummary {
  id: number;
  tenant_id: string;
  title: string;
  description: string;
  status: IncidentStatus;
  severity: AlertSeverity;
  alert_count: number;
  created_at: string;
  updated_at: string;
  opened_by: string;
  assigned_to: string | null;
  resolved_at: string | null;
}

export interface IncidentDetail extends IncidentSummary {
  alerts: Alert[];
}

export interface IncidentListPayload {
  items: IncidentSummary[];
}

export interface CreateIncidentRequest {
  title: string;
  description: string;
  severity: AlertSeverity;
  alert_ids?: number[];
  assigned_to?: string;
}

export interface UpdateIncidentRequest {
  status?: IncidentStatus;
  severity?: AlertSeverity;
  description?: string;
  assigned_to?: string | null;
}

export interface LinkAlertToIncidentRequest {
  alert_ids: number[];
}

// Webhooks
export interface WebhookConfig {
  id: number;
  tenant_id: string;
  url: string;
  events: WebhookEvent[];
  created_at: string;
  active: boolean;
}

export interface WebhookConfigRequest {
  url: string;
  events: WebhookEvent[];
}

export interface WebhookConfigPayload {
  items: WebhookConfig[];
}

// Wallet cluster / graph
export interface ClusterNode {
  address: string;
  chain: Blockchain;
  score: number;
  risk_level: RiskLevel;
  fingerprints: string[];
  confidence: number;
  entity_likelihood: number;
  last_active_at: string | null;
  activity_band: "low" | "moderate" | "high";
  is_root: boolean;
}

export interface ClusterHeuristicEvidence {
  heuristic:
    | "shared_funding_source"
    | "synchronized_activity"
    | "common_counterparty"
    | "cross_chain_link"
    | "behavioral_similarity";
  confidence: number;
  weight: number;
  description: string;
  related_addresses: string[];
}

export interface ClusterEdge {
  source: string;
  target: string;
  relation:
    | "shared_funding_source"
    | "synchronized_activity"
    | "common_counterparty"
    | "cross_chain_bridge"
    | "co_funded";
  strength: number;
  confidence: number;
  shared_counterparties: number;
  same_entity_likelihood: number;
  evidence: ClusterHeuristicEvidence[];
}

export interface WalletClusterResponse {
  cluster_id: string;
  root_address: string;
  nodes: ClusterNode[];
  edges: ClusterEdge[];
  heuristics: ClusterHeuristicEvidence[];
  confidence: number;
  cluster_score: number;
  cluster_risk: RiskLevel;
  cross_chain: boolean;
  last_updated_at: string;
  refresh_suggested_after_sec: number;
  narrative: string;
}

// Case management
export interface CaseSummary {
  id: number;
  tenant_id: string;
  title: string;
  status: CaseStatus;
  priority: CasePriority;
  summary: string;
  owner_email: string;
  source_type: string;
  source_ref: string;
  primary_chain: string;
  primary_address: string;
  risk_score: number;
  risk_level: RiskLevel;
  tags: string[];
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export interface CaseTimelineEvent {
  id: number;
  case_id: number;
  event_type: CaseEventType;
  actor_email: string;
  title: string;
  body: string;
  created_at: string;
}

export interface CaseNote {
  id: number;
  case_id: number;
  note_type: "observation" | "hypothesis" | "evidence" | "decision";
  body: string;
  tags: string[];
  author_email: string;
  created_at: string;
}

export interface CaseEntity {
  id: number;
  case_id: number;
  entity_type: CaseEntityType;
  label: string;
  chain: string;
  reference: string;
  risk_score: number | null;
  risk_level: RiskLevel | null;
  created_at: string;
}

export interface CaseAttachment {
  id: number;
  case_id: number;
  file_name: string;
  file_url: string;
  content_type: string;
  uploaded_by: string;
  created_at: string;
}

export interface CaseDetail extends CaseSummary {
  timeline: CaseTimelineEvent[];
  notes: CaseNote[];
  linked_entities: CaseEntity[];
  attachments: CaseAttachment[];
  activity: AuditEntry[];
}

export interface CaseListPayload {
  items: CaseSummary[];
}

export interface CreateCaseRequest {
  title: string;
  summary: string;
  priority: CasePriority;
  owner_email?: string;
  source_type?: string;
  source_ref?: string;
  primary_chain?: string;
  primary_address?: string;
  risk_score?: number;
  risk_level?: RiskLevel;
  tags?: string[];
}

export interface UpdateCaseRequest {
  status?: CaseStatus;
  priority?: CasePriority;
  summary?: string;
  owner_email?: string;
  tags?: string[];
}

export interface CreateCaseNoteRequest {
  note_type: "observation" | "hypothesis" | "evidence" | "decision";
  body: string;
  tags?: string[];
}

export interface CreateCaseEntityRequest {
  entity_type: CaseEntityType;
  label: string;
  chain?: string;
  reference: string;
  risk_score?: number;
  risk_level?: RiskLevel;
}

export interface CreateCaseAttachmentRequest {
  file_name: string;
  file_url: string;
  content_type?: string;
}



export interface AlertItem {
  id: string;
  timestamp: string;
  chain: Blockchain;
  title: string;
  severity: RiskLevel;
  score: number;
  wallet: string;
  amount_usd: number;
  summary: string;
}

export interface DashboardPayload {
  total_wallets_monitored: number;
  alerts_today: number;
  critical_alerts_today: number;
  avg_risk_score: number;
  trend_7d: number[];
  alerts: AlertItem[];
}

export interface WalletInput {
  chain: Blockchain;
  address: string;
  txn_24h: number;
  volume_24h_usd: number;
  sanctions_exposure_pct: number;
  mixer_exposure_pct: number;
  bridge_hops: number;
}

export interface WalletEnrichmentResponse extends WalletInput {
  source: string;
  fetched_at: string;
  asset_price_usd: number;
  balance_native: number;
  recent_tx_scanned: number;
  live_supported: boolean;
  notes: string[];
}

export interface WalletExplainResponse {
  analysis_id: number;
  chain: Blockchain;
  address: string;
  score: number;
  risk_level: RiskLevel;
  explanation: string;
}

export interface AnalysisEntry {
  id: number;
  created_at: string;
  chain: Blockchain;
  address: string;
  score: number;
  risk_level: RiskLevel;
  explanation: string;
  tags: string[];
}

export interface AnalysisHistoryPayload {
  items: AnalysisEntry[];
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface SignupEmailRequest {
  email: string;
  password: string;
  role?: UserRole;
}

export interface OAuthSignupRequest {
  provider: "google" | "apple";
  email: string;
}

export interface SignupBootstrapResponse {
  status: "ok";
  message: string;
}

export interface SetupStatusResponse {
  status: "ok";
  workspace_ready: boolean;
  user_count: number;
  first_signup_becomes_admin: boolean;
}

export interface PhoneSignupStartRequest {
  phone: string;
}

export interface PhoneSignupStartResponse {
  status: "ok";
  message: string;
  code_hint: string;
}

export interface PhoneSignupVerifyRequest {
  phone: string;
  code: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  tenant_id: string;
  email: string;
  role: UserRole;
}

export interface SessionInfo {
  email: string;
  tenant_id: string;
  role: UserRole;
}

export interface AuditEntry {
  id: number;
  created_at: string;
  actor_email: string;
  action: string;
  target: string;
  details: string;
}

export interface AuditHistoryPayload {
  items: AuditEntry[];
}

export interface TeamUser {
  id: number;
  email: string;
  tenant_id: string;
  role: UserRole;
  created_at: string;
}

export interface TeamUserCreateRequest {
  email: string;
  password: string;
  role: UserRole;
}

export interface TeamUserListPayload {
  items: TeamUser[];
}

export interface InviteCreateRequest {
  email: string;
  role: UserRole;
}

export interface InviteResponse {
  token: string;
  email: string;
  role: UserRole;
  expires_at: string;
}

export interface InviteEntry {
  token: string;
  email: string;
  tenant_id: string;
  role: UserRole;
  created_at: string;
  expires_at: string;
  used_at: string | null;
  revoked_at: string | null;
  status: InviteStatus;
}

export interface InviteListPayload {
  items: InviteEntry[];
}

export interface InviteRevokeResponse {
  token: string;
  revoked: boolean;
}

export interface InvitePublicStatusResponse {
  token: string;
  status: InviteStatus;
  email: string;
  role: UserRole;
  expires_at: string;
}

export interface AcceptInviteRequest {
  token: string;
  password: string;
}

export interface PasswordChangeRequest {
  current_password: string;
  new_password: string;
}

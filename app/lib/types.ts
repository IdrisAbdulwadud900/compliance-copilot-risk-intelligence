export type RiskLevel = "low" | "medium" | "high" | "critical";
export type UserRole = "admin" | "analyst" | "viewer";
export type InviteStatus = "active" | "used" | "expired" | "revoked";
export type Blockchain = "ethereum" | "solana" | "arbitrum" | "base" | "bsc" | "polygon";
export type RecommendedAction = "block" | "flag" | "monitor" | "watch";
export type AlertTrigger = "score_threshold" | "watchlist_activity" | "new_cluster_link" | "manual";
export type WebhookEvent = "alert.fired" | "wallet.flagged" | "watchlist.hit";

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

// Alert Events
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
}

export interface AlertEventPayload {
  items: AlertEvent[];
  unread_count: number;
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
  is_root: boolean;
}

export interface ClusterEdge {
  source: string;
  target: string;
  relation: string;
  strength: number;
}

export interface WalletClusterResponse {
  root_address: string;
  nodes: ClusterNode[];
  edges: ClusterEdge[];
  cluster_risk: number;
  narrative: string;
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

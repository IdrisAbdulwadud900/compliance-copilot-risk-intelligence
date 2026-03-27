import type {
  AuditEntry,
  AuditHistoryPayload,
  Alert,
  AlertFeedPayload,
  AlertSeverity,
  AlertType,
  AnalysisEntry,
  AnalysisHistoryPayload,
  CaseAttachment,
  CaseDetail,
  CaseEntity,
  CaseListPayload,
  CaseNote,
  CaseStatus,
  CreateAlertRequest,
  CreateCaseAttachmentRequest,
  CreateCaseEntityRequest,
  CreateCaseNoteRequest,
  CreateCaseRequest,
  CreateIncidentRequest,
  DashboardPayload,
  IncidentDetail,
  IncidentListPayload,
  IncidentStatus,
  InviteEntry,
  InviteCreateRequest,
  InviteListPayload,
  InvitePublicStatusResponse,
  InviteRevokeResponse,
  InviteResponse,
  LoginRequest,
  LoginResponse,
  OAuthSignupRequest,
  PasswordChangeRequest,
  PhoneSignupStartRequest,
  PhoneSignupStartResponse,
  PhoneSignupVerifyRequest,
  SessionInfo,
  SetupStatusResponse,
  SignupBootstrapResponse,
  SignupEmailRequest,
  TeamUser,
  TeamUserCreateRequest,
  TeamUserListPayload,
  UpdateAlertRequest,
  UpdateCaseRequest,
  UpdateIncidentRequest,
  WalletExplainResponse,
  WalletInput,
  WalletIntelligenceResponse,
  WatchlistEntry,
  WatchlistAddRequest,
  WatchlistPayload,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  AlertEvent,
  AlertEventPayload,
  WebhookConfig,
  WebhookConfigRequest,
  WebhookConfigPayload,
  WalletClusterResponse,
  WalletEnrichmentResponse,
} from "@/lib/types";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000").trim();
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";
export const PREVIEW_AUTH_ENABLED = ["1", "true", "yes", "on"].includes(
  (process.env.NEXT_PUBLIC_ENABLE_PREVIEW_AUTH ?? "").trim().toLowerCase(),
);
const TOKEN_KEY = "compliance_access_token";
const SESSION_KEY = "compliance_session_info";

function getStoredToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(TOKEN_KEY) ?? "";
}

export function saveAuthToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearAuthToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(SESSION_KEY);
}

export function hasAuthToken(): boolean {
  return getStoredToken().length > 0;
}

export function getSessionInfo(): SessionInfo | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(SESSION_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as SessionInfo;
  } catch {
    return null;
  }
}

function persistSession(data: LoginResponse): void {
  saveAuthToken(data.access_token);
  if (typeof window !== "undefined") {
    const session: SessionInfo = {
      email: data.email,
      tenant_id: data.tenant_id,
      role: data.role,
    };
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }
}

function authHeaders(includeJson = false): HeadersInit {
  const token = getStoredToken();
  const headers: HeadersInit = includeJson
    ? { "Content-Type": "application/json" }
    : {};

  if (token) {
    headers.Authorization = `Bearer ${token}`;
    return headers;
  }

  if (API_KEY.trim()) {
    headers["x-api-key"] = API_KEY;
  }
  return headers;
}

async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: string | Array<{ loc?: Array<string | number>; msg?: string }>;
      message?: string;
    };

    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }

    if (Array.isArray(payload.detail) && payload.detail.length > 0) {
      return payload.detail
        .map((item) => item.msg ?? `${item.loc?.join(".") ?? "field"} is invalid`)
        .join("; ");
    }

    if (typeof payload.message === "string" && payload.message.trim()) {
      return payload.message;
    }
  } catch {
    try {
      const text = await response.text();
      if (text.trim()) {
        return text.trim();
      }
    } catch {
      return `${fallback} (${response.status})`;
    }
  }

  return `${fallback} (${response.status})`;
}

export async function getDashboard(): Promise<DashboardPayload> {
  const response = await fetch(`${API_BASE}/dashboard`, {
    cache: "no-store",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Dashboard request failed: ${response.status}`);
  return (await response.json()) as DashboardPayload;
}

export async function explainWallet(payload: WalletInput): Promise<WalletExplainResponse> {
  const response = await fetch(`${API_BASE}/wallets/explain`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Explain request failed: ${response.status}`);
  }

  return (await response.json()) as WalletExplainResponse;
}

export async function getAnalyses(limit = 20): Promise<AnalysisEntry[]> {
  const response = await fetch(`${API_BASE}/analyses?limit=${limit}`, {
    cache: "no-store",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Analyses request failed: ${response.status}`);
  const payload = (await response.json()) as AnalysisHistoryPayload;
  return payload.items;
}

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Could not sign in"));
  }

  const data = (await response.json()) as LoginResponse;
  persistSession(data);
  return data;
}

export async function signupWithEmail(payload: SignupEmailRequest): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Could not create your workspace"));
  }

  const data = (await response.json()) as LoginResponse;
  persistSession(data);
  return data;
}

export async function getSetupStatus(): Promise<SetupStatusResponse> {
  const response = await fetch(`${API_BASE}/auth/setup-status`, {
    cache: "no-store",
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Could not load workspace setup status"));
  }

  return (await response.json()) as SetupStatusResponse;
}

export async function signupWithOAuth(payload: OAuthSignupRequest): Promise<SignupBootstrapResponse> {
  const response = await fetch(`${API_BASE}/auth/signup/oauth`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Could not prepare the SSO preview"));
  }

  return (await response.json()) as SignupBootstrapResponse;
}

export async function startPhoneSignup(payload: PhoneSignupStartRequest): Promise<PhoneSignupStartResponse> {
  const response = await fetch(`${API_BASE}/auth/signup/phone/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Could not generate a preview phone code"));
  }

  return (await response.json()) as PhoneSignupStartResponse;
}

export async function verifyPhoneSignup(payload: PhoneSignupVerifyRequest): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/auth/signup/phone/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Could not verify the preview phone code"));
  }

  const data = (await response.json()) as LoginResponse;
  persistSession(data);
  return data;
}

export async function getAuditLogs(limit = 25): Promise<AuditEntry[]> {
  const response = await fetch(`${API_BASE}/audit-logs?limit=${limit}`, {
    cache: "no-store",
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Audit logs request failed: ${response.status}`);
  }

  const payload = (await response.json()) as AuditHistoryPayload;
  return payload.items;
}

export async function getTeamUsers(): Promise<TeamUser[]> {
  const response = await fetch(`${API_BASE}/users`, {
    cache: "no-store",
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Team users request failed: ${response.status}`);
  }

  const payload = (await response.json()) as TeamUserListPayload;
  return payload.items;
}

export async function createTeamUser(payload: TeamUserCreateRequest): Promise<TeamUser> {
  const response = await fetch(`${API_BASE}/users`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Create user failed: ${response.status}`);
  }

  return (await response.json()) as TeamUser;
}

export async function createInvite(payload: InviteCreateRequest): Promise<InviteResponse> {
  const response = await fetch(`${API_BASE}/users/invite`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Create invite failed: ${response.status}`);
  }

  return (await response.json()) as InviteResponse;
}

export async function getInvites(limit = 50): Promise<InviteEntry[]> {
  const response = await fetch(`${API_BASE}/users/invites?limit=${limit}`, {
    cache: "no-store",
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Invite list request failed: ${response.status}`);
  }

  const payload = (await response.json()) as InviteListPayload;
  return payload.items;
}

export async function revokeInvite(token: string): Promise<InviteRevokeResponse> {
  const response = await fetch(`${API_BASE}/users/invites/${encodeURIComponent(token)}`, {
    method: "DELETE",
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Invite revoke failed: ${response.status}`);
  }

  return (await response.json()) as InviteRevokeResponse;
}

export async function acceptInvite(token: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/auth/accept-invite`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, password }),
  });

  if (!response.ok) {
    throw new Error(`Accept invite failed: ${response.status}`);
  }

  const data = (await response.json()) as LoginResponse;
  saveAuthToken(data.access_token);
  if (typeof window !== "undefined") {
    const session: SessionInfo = {
      email: data.email,
      tenant_id: data.tenant_id,
      role: data.role,
    };
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }
  return data;
}

export async function getInviteStatus(token: string): Promise<InvitePublicStatusResponse> {
  const response = await fetch(`${API_BASE}/auth/invite-status?token=${encodeURIComponent(token)}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Invite status failed: ${response.status}`);
  }

  return (await response.json()) as InvitePublicStatusResponse;
}

export async function changePassword(payload: PasswordChangeRequest): Promise<void> {
  const response = await fetch(`${API_BASE}/auth/change-password`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Change password failed: ${response.status}`);
  }
}

export async function updateAnalysisTags(
  analysisId: number,
  tags: string[]
): Promise<AnalysisEntry> {
  const response = await fetch(`${API_BASE}/analyses/${analysisId}/tags`, {
    method: "PATCH",
    headers: authHeaders(true),
    body: JSON.stringify({ tags }),
  });

  if (!response.ok) {
    throw new Error(`Tag update failed: ${response.status}`);
  }

  return (await response.json()) as AnalysisEntry;
}

export async function exportAnalysesCSV(limit = 500): Promise<void> {
  const response = await fetch(`${API_BASE}/analyses/export?limit=${limit}`, {
    cache: "no-store",
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new Error(`CSV export failed: ${response.status}`);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename=([^;]+)/);
  a.download = match ? match[1] : "compliance_export.csv";
  a.href = url;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ─── Intelligence ────────────────────────────────────────────────────────────

export async function analyzeWalletIntelligence(
  payload: WalletInput
): Promise<WalletIntelligenceResponse> {
  const response = await fetch(`${API_BASE}/wallets/intelligence`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Intelligence request failed: ${response.status}`);
  return (await response.json()) as WalletIntelligenceResponse;
}

export async function enrichWalletInput(
  address: string,
  chain = "ethereum"
): Promise<WalletEnrichmentResponse> {
  const response = await fetch(
    `${API_BASE}/wallets/${encodeURIComponent(address)}/enrich?chain=${encodeURIComponent(chain)}`,
    { cache: "no-store", headers: authHeaders() }
  );
  if (!response.ok) throw new Error(`Live enrichment failed: ${response.status}`);
  return (await response.json()) as WalletEnrichmentResponse;
}

export async function getWalletCluster(
  address: string,
  chain = "ethereum",
  context?: Partial<Pick<WalletInput, "txn_24h" | "volume_24h_usd" | "sanctions_exposure_pct" | "mixer_exposure_pct" | "bridge_hops">>
): Promise<WalletClusterResponse> {
  const params = new URLSearchParams({ chain });
  if (context?.txn_24h !== undefined) params.set("txn_24h", String(context.txn_24h));
  if (context?.volume_24h_usd !== undefined) params.set("volume_24h_usd", String(context.volume_24h_usd));
  if (context?.sanctions_exposure_pct !== undefined) params.set("sanctions_exposure_pct", String(context.sanctions_exposure_pct));
  if (context?.mixer_exposure_pct !== undefined) params.set("mixer_exposure_pct", String(context.mixer_exposure_pct));
  if (context?.bridge_hops !== undefined) params.set("bridge_hops", String(context.bridge_hops));
  const response = await fetch(
    `${API_BASE}/wallets/${encodeURIComponent(address)}/cluster?${params.toString()}`,
    { cache: "no-store", headers: authHeaders() }
  );
  if (!response.ok) throw new Error(`Cluster request failed: ${response.status}`);
  return (await response.json()) as WalletClusterResponse;
}

// ─── Cases ───────────────────────────────────────────────────────────────────

export async function getCases(limit = 50, status?: CaseStatus): Promise<CaseListPayload> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set("status", status);

  const response = await fetch(`${API_BASE}/cases?${params.toString()}`, {
    cache: "no-store",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Cases request failed: ${response.status}`);
  return (await response.json()) as CaseListPayload;
}

export async function getCase(caseId: number): Promise<CaseDetail> {
  const response = await fetch(`${API_BASE}/cases/${caseId}`, {
    cache: "no-store",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Case detail request failed: ${response.status}`);
  return (await response.json()) as CaseDetail;
}

export async function createCase(payload: CreateCaseRequest): Promise<CaseDetail> {
  const response = await fetch(`${API_BASE}/cases`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Create case failed: ${response.status}`);
  return (await response.json()) as CaseDetail;
}

export async function updateCase(caseId: number, payload: UpdateCaseRequest): Promise<CaseDetail> {
  const response = await fetch(`${API_BASE}/cases/${caseId}`, {
    method: "PATCH",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Update case failed: ${response.status}`);
  return (await response.json()) as CaseDetail;
}

export async function addCaseNote(caseId: number, payload: CreateCaseNoteRequest): Promise<CaseNote> {
  const response = await fetch(`${API_BASE}/cases/${caseId}/notes`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Add case note failed: ${response.status}`);
  return (await response.json()) as CaseNote;
}

export async function addCaseEntity(caseId: number, payload: CreateCaseEntityRequest): Promise<CaseEntity> {
  const response = await fetch(`${API_BASE}/cases/${caseId}/entities`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Add case entity failed: ${response.status}`);
  return (await response.json()) as CaseEntity;
}

export async function addCaseAttachment(caseId: number, payload: CreateCaseAttachmentRequest): Promise<CaseAttachment> {
  const response = await fetch(`${API_BASE}/cases/${caseId}/attachments`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Add case attachment failed: ${response.status}`);
  return (await response.json()) as CaseAttachment;
}

// ─── Alerts v2 ───────────────────────────────────────────────────────────────

export async function getAlerts(params?: {
  severity?: AlertSeverity;
  alert_type?: AlertType;
  unacked_only?: boolean;
  incident_id?: number;
  since_id?: number;
  limit?: number;
}): Promise<AlertEventPayload> {
  const p = new URLSearchParams();
  if (params?.severity) p.set("severity", params.severity);
  if (params?.alert_type) p.set("alert_type", params.alert_type);
  if (params?.unacked_only) p.set("unacked_only", "true");
  if (params?.incident_id !== undefined) p.set("incident_id", String(params.incident_id));
  if (params?.since_id !== undefined) p.set("since_id", String(params.since_id));
  if (params?.limit !== undefined) p.set("limit", String(params.limit));
  const response = await fetch(`${API_BASE}/alerts?${p.toString()}`, {
    cache: "no-store",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Get alerts failed: ${response.status}`);
  return (await response.json()) as AlertEventPayload;
}

export async function createAlertManual(payload: CreateAlertRequest): Promise<Alert> {
  const response = await fetch(`${API_BASE}/alerts`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Create alert failed: ${response.status}`);
  return (await response.json()) as Alert;
}

export async function ackAlertV2(alertId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/alerts/${alertId}/ack`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Ack alert v2 failed: ${response.status}`);
}

export async function ackAllAlertsV2(): Promise<{ acked: number }> {
  const response = await fetch(`${API_BASE}/alerts/ack-all`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Ack all alerts failed: ${response.status}`);
  return (await response.json()) as { acked: number };
}

export async function resolveAlert(alertId: number, payload: UpdateAlertRequest): Promise<Alert> {
  const response = await fetch(`${API_BASE}/alerts/${alertId}`, {
    method: "PATCH",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Resolve alert failed: ${response.status}`);
  return (await response.json()) as Alert;
}

export async function getAlertsFeed(sinceId = 0, limit = 50): Promise<AlertFeedPayload> {
  const response = await fetch(
    `${API_BASE}/alerts/feed?since_id=${sinceId}&limit=${limit}`,
    { cache: "no-store", headers: authHeaders() }
  );
  if (!response.ok) throw new Error(`Alert feed failed: ${response.status}`);
  return (await response.json()) as AlertFeedPayload;
}

// ─── Incidents ────────────────────────────────────────────────────────────────

export async function getIncidents(params?: {
  status?: IncidentStatus;
  severity?: AlertSeverity;
  limit?: number;
}): Promise<IncidentListPayload> {
  const p = new URLSearchParams();
  if (params?.status) p.set("status", params.status);
  if (params?.severity) p.set("severity", params.severity);
  if (params?.limit !== undefined) p.set("limit", String(params.limit));
  const response = await fetch(`${API_BASE}/incidents?${p.toString()}`, {
    cache: "no-store",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Get incidents failed: ${response.status}`);
  return (await response.json()) as IncidentListPayload;
}

export async function createIncident(payload: CreateIncidentRequest): Promise<IncidentDetail> {
  const response = await fetch(`${API_BASE}/incidents`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Create incident failed: ${response.status}`);
  return (await response.json()) as IncidentDetail;
}

export async function getIncidentDetail(id: number): Promise<IncidentDetail> {
  const response = await fetch(`${API_BASE}/incidents/${id}`, {
    cache: "no-store",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Get incident failed: ${response.status}`);
  return (await response.json()) as IncidentDetail;
}

export async function updateIncident(id: number, payload: UpdateIncidentRequest): Promise<IncidentDetail> {
  const response = await fetch(`${API_BASE}/incidents/${id}`, {
    method: "PATCH",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Update incident failed: ${response.status}`);
  return (await response.json()) as IncidentDetail;
}

export async function linkAlertsToIncident(incidentId: number, alertIds: number[]): Promise<IncidentDetail> {
  const response = await fetch(`${API_BASE}/incidents/${incidentId}/alerts`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({ alert_ids: alertIds }),
  });
  if (!response.ok) throw new Error(`Link alerts to incident failed: ${response.status}`);
  return (await response.json()) as IncidentDetail;
}

export async function unlinkAlertFromIncident(incidentId: number, alertId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/incidents/${incidentId}/alerts/${alertId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Unlink alert from incident failed: ${response.status}`);
}

// ─── Watchlist ────────────────────────────────────────────────────────────────

export async function getWatchlist(): Promise<WatchlistEntry[]> {
  const response = await fetch(`${API_BASE}/watchlist`, {
    cache: "no-store",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Watchlist request failed: ${response.status}`);
  const payload = (await response.json()) as WatchlistPayload;
  return payload.items;
}

export async function addToWatchlist(payload: WatchlistAddRequest): Promise<WatchlistEntry> {
  const response = await fetch(`${API_BASE}/watchlist`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Add to watchlist failed: ${response.status}`);
  return (await response.json()) as WatchlistEntry;
}

export async function removeFromWatchlist(id: number): Promise<void> {
  const response = await fetch(`${API_BASE}/watchlist/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Remove from watchlist failed: ${response.status}`);
}

// ─── Alert Events ─────────────────────────────────────────────────────────────

export async function getAlertEvents(
  limit = 50,
  unackedOnly = false
): Promise<AlertEventPayload> {
  const response = await fetch(
    `${API_BASE}/alert-events?limit=${limit}&unacked_only=${unackedOnly}`,
    { cache: "no-store", headers: authHeaders() }
  );
  if (!response.ok) throw new Error(`Alert events request failed: ${response.status}`);
  return (await response.json()) as AlertEventPayload;
}

export async function acknowledgeAlert(alertId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/alert-events/${alertId}/ack`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Ack alert failed: ${response.status}`);
}

// ─── Webhooks ─────────────────────────────────────────────────────────────────

export async function getWebhooks(): Promise<WebhookConfig[]> {
  const response = await fetch(`${API_BASE}/webhooks`, {
    cache: "no-store",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Webhooks request failed: ${response.status}`);
  const payload = (await response.json()) as WebhookConfigPayload;
  return payload.items;
}

export async function createWebhook(payload: WebhookConfigRequest): Promise<WebhookConfig> {
  const response = await fetch(`${API_BASE}/webhooks`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Create webhook failed: ${response.status}`);
  return (await response.json()) as WebhookConfig;
}

export async function deleteWebhook(id: number): Promise<void> {
  const response = await fetch(`${API_BASE}/webhooks/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Delete webhook failed: ${response.status}`);
}


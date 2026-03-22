import type {
  AuditEntry,
  AuditHistoryPayload,
  AnalysisEntry,
  AnalysisHistoryPayload,
  DashboardPayload,
  InviteEntry,
  InviteCreateRequest,
  InviteListPayload,
  InvitePublicStatusResponse,
  InviteRevokeResponse,
  InviteResponse,
  LoginRequest,
  LoginResponse,
  PasswordChangeRequest,
  SessionInfo,
  TeamUser,
  TeamUserCreateRequest,
  TeamUserListPayload,
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
} from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "demo-key";
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

function authHeaders(includeJson = false): HeadersInit {
  const token = getStoredToken();
  const headers: HeadersInit = includeJson
    ? { "Content-Type": "application/json" }
    : {};

  if (token) {
    headers.Authorization = `Bearer ${token}`;
    return headers;
  }

  headers["x-api-key"] = API_KEY;
  return headers;
}

const demoFallback: DashboardPayload = {
  total_wallets_monitored: 148,
  alerts_today: 23,
  critical_alerts_today: 2,
  avg_risk_score: 46.8,
  trend_7d: [12, 14, 11, 16, 19, 17, 23],
  alerts: [
    {
      id: "alrt_1",
      timestamp: new Date().toISOString(),
      chain: "ethereum",
      title: "Potential sanctions-linked inflow",
      severity: "critical",
      score: 91,
      wallet: "0xA91f...D2C1",
      amount_usd: 842100,
      summary: "Immediate review required",
    },
    {
      id: "alrt_2",
      timestamp: new Date().toISOString(),
      chain: "arbitrum",
      title: "Mixer-adjacent transaction spike",
      severity: "high",
      score: 77,
      wallet: "0x7B31...A981",
      amount_usd: 213440,
      summary: "Increased obfuscation pattern",
    },
  ],
};

const demoHistory: AnalysisEntry[] = [
  {
    id: 1,
    created_at: new Date().toISOString(),
    chain: "ethereum",
    address: "0xA91fCC88d2C14FA91123",
    score: 74,
    risk_level: "high",
    explanation:
      "High urgency: wallet 0xA91fCC88... scored 74/100 due to material sanctions exposure.",
    tags: [],
  },
  {
    id: 2,
    created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    chain: "base",
    address: "0x7B31B0B1AA81",
    score: 42,
    risk_level: "medium",
    explanation:
      "Medium risk: wallet 0x7B31B0B1... scored 42/100 from notable mixer proximity.",
    tags: [],
  },
];

export async function getDashboard(): Promise<DashboardPayload> {
  try {
    const response = await fetch(`${API_BASE}/dashboard`, {
      cache: "no-store",
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error(`Dashboard request failed: ${response.status}`);
    return (await response.json()) as DashboardPayload;
  } catch {
    return demoFallback;
  }
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
  try {
    const response = await fetch(`${API_BASE}/analyses?limit=${limit}`, {
      cache: "no-store",
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error(`Analyses request failed: ${response.status}`);
    const payload = (await response.json()) as AnalysisHistoryPayload;
    return payload.items;
  } catch {
    return demoHistory;
  }
}

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Login failed: ${response.status}`);
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

export async function getWalletCluster(
  address: string,
  chain = "ethereum"
): Promise<WalletClusterResponse> {
  const response = await fetch(
    `${API_BASE}/wallets/${encodeURIComponent(address)}/cluster?chain=${chain}`,
    { cache: "no-store", headers: authHeaders() }
  );
  if (!response.ok) throw new Error(`Cluster request failed: ${response.status}`);
  return (await response.json()) as WalletClusterResponse;
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


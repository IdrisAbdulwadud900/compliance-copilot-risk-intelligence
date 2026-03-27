"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import {
  Activity,
  Apple,
  AlertTriangle,
  BadgeDollarSign,
  Bell,
  BellOff,
  BookmarkPlus,
  Chrome,
  ChevronDown,
  ChevronUp,
  Download,
  Eye,
  Globe,
  LockKeyhole,
  PanelRightClose,
  PanelRightOpen,
  Search,
  ShieldCheck,
  Sparkles,
  Tag,
  Trash2,
  Webhook,
  X,
  Zap,
  LogOut,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";
import { formatDistanceToNow } from "date-fns";

import {
  acknowledgeAlert,
  ackAlertV2,
  ackAllAlertsV2,
  addCaseAttachment,
  addCaseEntity,
  addCaseNote,
  addToWatchlist,
  analyzeWalletIntelligence,
  changePassword,
  createAlertManual,
  createCase,
  clearAuthToken,
  createIncident,
  createInvite,
  createTeamUser,
  createWebhook,
  deleteWebhook,
  exportAnalysesCSV,
  enrichWalletInput,
  getAlertEvents,
  getAlerts,
  getAnalyses,
  getAuditLogs,
  getCase,
  getCases,
  getDashboard,
  getIncidentDetail,
  getIncidents,
  getInvites,
  getSetupStatus,
  getSessionInfo,
  getTeamUsers,
  getWalletCluster,
  getWatchlist,
  getWebhooks,
  hasAuthToken,
  login,
  PREVIEW_AUTH_ENABLED,
  removeFromWatchlist,
  resolveAlert,
  revokeInvite,
  signupWithEmail,
  signupWithOAuth,
  startPhoneSignup,
  updateCase,
  updateIncident,
  updateAnalysisTags,
  verifyPhoneSignup,
} from "@/lib/api";
import type {
  Alert,
  AlertEvent,
  AlertSeverity,
  AlertType,
  AnalysisEntry,
  AuditEntry,
  Blockchain,
  CaseDetail,
  CaseEntityType,
  CasePriority,
  CaseStatus,
  CaseSummary,
  ClusterEdge,
  ClusterHeuristicEvidence,
  ClusterNode,
  DashboardPayload,
  IncidentDetail,
  IncidentStatus,
  IncidentSummary,
  InviteEntry,
  LoginRequest,
  PasswordChangeRequest,
  SessionInfo,
  SetupStatusResponse,
  TeamUser,
  TeamUserCreateRequest,
  WalletClusterResponse,
  WalletEnrichmentResponse,
  WalletInput,
  WalletIntelligenceResponse,
  WatchlistEntry,
  WebhookConfig,
  WebhookEvent,
} from "@/lib/types";

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message.trim() ? error.message : fallback;
}
import { cn, riskTone } from "@/lib/utils";

const initialWalletInput: WalletInput = {
  chain: "ethereum",
  address: "0xA91fCC88d2C14FA91123",
  txn_24h: 182,
  volume_24h_usd: 315000,
  sanctions_exposure_pct: 9,
  mixer_exposure_pct: 15,
  bridge_hops: 4,
};

const chainOptions: Blockchain[] = ["ethereum", "solana", "arbitrum", "base", "bsc", "polygon"];

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#f43f5e",
  high: "#f97316",
  medium: "#eab308",
  low: "#22c55e",
};

const ACTION_STYLES: Record<string, string> = {
  block: "border-rose-500/50 bg-rose-500/15 text-rose-200",
  flag: "border-orange-500/50 bg-orange-500/15 text-orange-200",
  monitor: "border-amber-500/50 bg-amber-500/15 text-amber-200",
  watch: "border-blue-500/50 bg-blue-500/15 text-blue-200",
};

const PRESET_TAGS = [
  "under-review",
  "sanctions-risk",
  "mixer-flagged",
  "false-positive",
  "escalated",
  "cleared",
];

const WEBHOOK_EVENTS: WebhookEvent[] = ["alert.fired", "wallet.flagged", "watchlist.hit"];

const SAMPLE_WALLET_PRESETS: Array<{
  title: string;
  chain: Blockchain;
  address: string;
  category: string;
  sourceLabel: string;
  description: string;
  walletInput: WalletInput;
}> = [
  {
    title: "Vitalik EOA wallet",
    chain: "ethereum",
    address: "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
    category: "Individual wallet",
    sourceLabel: "Live Ethereum",
    description: "Useful for validating a known public wallet with live activity, narrative output, and honest low-risk clustering.",
    walletInput: {
      chain: "ethereum",
      address: "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
      txn_24h: 24,
      volume_24h_usd: 185000,
      sanctions_exposure_pct: 1,
      mixer_exposure_pct: 0,
      bridge_hops: 1,
    },
  },
  {
    title: "Binance hot wallet",
    chain: "ethereum",
    address: "0x28C6c06298d514Db089934071355E5743bf21d60",
    category: "Exchange wallet",
    sourceLabel: "Live Ethereum",
    description: "Best for seeing why high-throughput operational wallets trigger stronger risk context, watchlist alerts, and counterparty clusters.",
    walletInput: {
      chain: "ethereum",
      address: "0x28C6c06298d514Db089934071355E5743bf21d60",
      txn_24h: 640,
      volume_24h_usd: 4200000,
      sanctions_exposure_pct: 7,
      mixer_exposure_pct: 2,
      bridge_hops: 3,
    },
  },
  {
    title: "USDC contract",
    chain: "ethereum",
    address: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    category: "Token contract",
    sourceLabel: "Live Ethereum",
    description: "Shows graceful handling for busy contracts where enrichment works but clustering may intentionally collapse to the root node.",
    walletInput: {
      chain: "ethereum",
      address: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
      txn_24h: 990,
      volume_24h_usd: 9800000,
      sanctions_exposure_pct: 3,
      mixer_exposure_pct: 0,
      bridge_hops: 1,
    },
  },
];

const COVERAGE_NOTES = [
  {
    chain: "Ethereum",
    mode: "Live public-chain enrichment, live counterparty clustering, and strongest out-of-the-box analyst experience.",
  },
  {
    chain: "Arbitrum · Base · BSC · Polygon",
    mode: "Analyst-driven scoring and workflow coverage today, ready for richer live connectors as data sources are added.",
  },
  {
    chain: "Solana",
    mode: "Manual intake, intelligence scoring, watchlist, alerts, incidents, and case handling already work for non-EVM investigations.",
  },
];

export default function Home() {
  // Core state
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [isMounted, setIsMounted] = useState(false);
  const [analyses, setAnalyses] = useState<AnalysisEntry[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditEntry[]>([]);
  const [teamUsers, setTeamUsers] = useState<TeamUser[]>([]);
  const [invites, setInvites] = useState<InviteEntry[]>([]);
  const [lastAdminRefreshAt, setLastAdminRefreshAt] = useState("");

  // Cases
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [activeCase, setActiveCase] = useState<CaseDetail | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);
  const [caseFilter, setCaseFilter] = useState<"all" | CaseStatus>("all");
  const [caseBusy, setCaseBusy] = useState(false);
  const [caseError, setCaseError] = useState("");
  const [caseMessage, setCaseMessage] = useState("");
  const [caseForm, setCaseForm] = useState({
    title: "",
    summary: "",
    priority: "high" as CasePriority,
    tags: "",
  });
  const [caseNoteForm, setCaseNoteForm] = useState({
    note_type: "observation" as "observation" | "hypothesis" | "evidence" | "decision",
    body: "",
    tags: "",
  });
  const [caseEntityForm, setCaseEntityForm] = useState({
    entity_type: "wallet" as CaseEntityType,
    label: "",
    chain: "ethereum",
    reference: "",
  });
  const [caseAttachmentForm, setCaseAttachmentForm] = useState({
    file_name: "",
    file_url: "",
    content_type: "link",
  });

  // Auth
  const [auth, setAuth] = useState<LoginRequest>({ email: "", password: "" });
  const [authError, setAuthError] = useState("");
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [authMode, setAuthMode] = useState<"signin" | "signup">("signin");
  const [signupForm, setSignupForm] = useState({ email: "", password: "", confirmPassword: "", phone: "", code: "" });
  const [signupBusy, setSignupBusy] = useState(false);
  const [signupMessage, setSignupMessage] = useState("");
  const [demoCodeHint, setDemoCodeHint] = useState("");
  const [setupStatus, setSetupStatus] = useState<SetupStatusResponse | null>(null);
  const [loggedIn, setLoggedIn] = useState(false);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [passwordForm, setPasswordForm] = useState<PasswordChangeRequest>({ current_password: "", new_password: "" });
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState("");

  // Team / invites
  const [teamForm, setTeamForm] = useState<TeamUserCreateRequest>({ email: "", password: "", role: "analyst" });
  const [teamError, setTeamError] = useState("");
  const [teamBusy, setTeamBusy] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<TeamUserCreateRequest["role"]>("analyst");
  const [inviteToken, setInviteToken] = useState("");
  const [inviteLink, setInviteLink] = useState("");
  const [inviteExpiresAt, setInviteExpiresAt] = useState("");
  const [inviteCopied, setInviteCopied] = useState("");
  const [inviteNowMs, setInviteNowMs] = useState(Date.now());
  const [inviteError, setInviteError] = useState("");
  const [inviteBusy, setInviteBusy] = useState(false);
  const [inviteListBusy, setInviteListBusy] = useState(false);
  const [inviteActionMessage, setInviteActionMessage] = useState("");
  const [revokingToken, setRevokingToken] = useState("");

  // Wallet intelligence
  const [walletInput, setWalletInput] = useState<WalletInput>(initialWalletInput);
  const [intelligence, setIntelligence] = useState<WalletIntelligenceResponse | null>(null);
  const [loadingIntel, setLoadingIntel] = useState(false);
  const [loadingEnrich, setLoadingEnrich] = useState(false);
  const [liveEnrichment, setLiveEnrichment] = useState<WalletEnrichmentResponse | null>(null);
  const [intelError, setIntelError] = useState("");
  const [showCluster, setShowCluster] = useState(false);
  const [cluster, setCluster] = useState<WalletClusterResponse | null>(null);
  const [loadingCluster, setLoadingCluster] = useState(false);

  // Tags
  const [taggingId, setTaggingId] = useState<number | null>(null);
  const [tagInput, setTagInput] = useState("");
  const [tagBusy, setTagBusy] = useState(false);
  const [tagMessage, setTagMessage] = useState("");

  // CSV
  const [csvBusy, setCsvBusy] = useState(false);
  const [csvMessage, setCsvMessage] = useState("");

  // Watchlist
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [watchlistBusy, setWatchlistBusy] = useState(false);
  const [watchlistError, setWatchlistError] = useState("");
  const [watchForm, setWatchForm] = useState({ address: "", label: "", chain: "ethereum" as Blockchain });

  // Active tab
  const [activeTab, setActiveTab] = useState<"dashboard" | "alerts" | "incidents">("dashboard");

  // Alerts (legacy alert-events panel on dashboard)
  const [alertEvents, setAlertEvents] = useState<AlertEvent[]>([]);
  const [alertUnread, setAlertUnread] = useState(0);
  const [alertBusy, setAlertBusy] = useState(false);
  const [showUnackedOnly, setShowUnackedOnly] = useState(false);

  // Alerts v2 (dedicated Alerts tab)
  const [alertsV2, setAlertsV2] = useState<Alert[]>([]);
  const [alertsV2Unread, setAlertsV2Unread] = useState(0);
  const [alertsV2Loading, setAlertsV2Loading] = useState(false);
  const [alertsV2Filter, setAlertsV2Filter] = useState<{
    severity: string;
    alert_type: string;
    unacked_only: boolean;
  }>({ severity: "", alert_type: "", unacked_only: false });
  const [alertsV2Error, setAlertsV2Error] = useState("");
  const [alertsV2Message, setAlertsV2Message] = useState("");
  const [manualAlertForm, setManualAlertForm] = useState({
    title: "",
    body: "",
    severity: "high" as AlertSeverity,
    alert_type: "manual" as AlertType,
    chain: "ethereum" as Blockchain,
    address: "",
    score: 70,
  });
  const [manualAlertBusy, setManualAlertBusy] = useState(false);

  // Incidents
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [activeIncident, setActiveIncident] = useState<IncidentDetail | null>(null);
  const [selectedIncidentId, setSelectedIncidentId] = useState<number | null>(null);
  const [incidentsLoading, setIncidentsLoading] = useState(false);
  const [incidentForm, setIncidentForm] = useState({
    title: "",
    description: "",
    severity: "high" as AlertSeverity,
  });
  const [incidentBusy, setIncidentBusy] = useState(false);
  const [incidentError, setIncidentError] = useState("");
  const [incidentMessage, setIncidentMessage] = useState("");
  const [incidentStatusFilter, setIncidentStatusFilter] = useState<"all" | IncidentStatus>("all");

  const [commandRailCollapsed, setCommandRailCollapsed] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");

  // Webhooks
  const [webhooks, setWebhooks] = useState<WebhookConfig[]>([]);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookEvents, setWebhookEvents] = useState<WebhookEvent[]>(["alert.fired"]);
  const [webhookBusy, setWebhookBusy] = useState(false);
  const [webhookError, setWebhookError] = useState("");

  // ─── Init ──────────────────────────────────────────────────────────────────

  const refreshIntelPanels = useCallback(async (role: string) => {
    try {
      const alerts = await getAlertEvents(50);
      setAlertEvents(alerts.items);
      setAlertUnread(alerts.unread_count);
      const wl = await getWatchlist();
      setWatchlist(wl);
    } catch { /* swallow */ }
    if (role === "admin") {
      try {
        const [logs, users, pendingInvites, hooks] = await Promise.all([
          getAuditLogs(8), getTeamUsers(), getInvites(15), getWebhooks(),
        ]);
        setAuditLogs(logs);
        setTeamUsers(users);
        setInvites(pendingInvites);
        setWebhooks(hooks);
        setLastAdminRefreshAt(new Date().toISOString());
      } catch { /* swallow */ }
    }
  }, []);

  const refreshCases = useCallback(async (preferredCaseId?: number | null) => {
    if (!hasAuthToken()) {
      setCases([]);
      setActiveCase(null);
      setSelectedCaseId(null);
      return;
    }

    try {
      const payload = await getCases(24, caseFilter === "all" ? undefined : caseFilter);
      setCases(payload.items);

      const selectedStillVisible = selectedCaseId ? payload.items.some((item) => item.id === selectedCaseId) : false;
      const nextCaseId = preferredCaseId ?? (selectedStillVisible ? selectedCaseId : payload.items[0]?.id ?? null);
      setSelectedCaseId(nextCaseId);

      if (nextCaseId) {
        const detail = await getCase(nextCaseId);
        setActiveCase(detail);
      } else {
        setActiveCase(null);
      }

      setCaseError("");
    } catch {
      setCaseError("Could not load investigations.");
    }
  }, [caseFilter, selectedCaseId]);

  useEffect(() => {
    if (!loggedIn) return;
    refreshCases();
  }, [caseFilter, loggedIn, refreshCases]);

  useEffect(() => {
    setIsMounted(true);
    getDashboard().then(setDashboard).catch(() => setDashboard(null));
    getAnalyses(20).then(setAnalyses).catch(() => setAnalyses([]));
    getSetupStatus().then(setSetupStatus).catch(() => setSetupStatus(null));
    const loggedInNow = hasAuthToken();
    setLoggedIn(loggedInNow);
    const s = getSessionInfo();
    setSession(s);
    if (loggedInNow && s) {
      refreshIntelPanels(s.role);
      refreshCases();
    }
  }, [refreshCases, refreshIntelPanels]);

  // Auto-refresh every 15s
  useEffect(() => {
    if (!loggedIn) return;
    const iv = window.setInterval(() => {
      getAlertEvents(50)
        .then((p) => { setAlertEvents(p.items); setAlertUnread(p.unread_count); })
        .catch(() => {});
      refreshCases();
      if (session?.role === "admin") {
        Promise.all([getAuditLogs(8), getTeamUsers(), getInvites(15)])
          .then(([logs, users, pendingInvites]) => {
            setAuditLogs(logs); setTeamUsers(users); setInvites(pendingInvites);
            setLastAdminRefreshAt(new Date().toISOString());
          }).catch(() => {});
      }
    }, 15000);
    return () => window.clearInterval(iv);
  }, [loggedIn, refreshCases, session?.role]);

  // Invite expiry countdown
  useEffect(() => {
    if (!inviteExpiresAt) return;
    const timer = window.setInterval(() => setInviteNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [inviteExpiresAt]);

  // ─── Derived ───────────────────────────────────────────────────────────────

  const trendData = useMemo(
    () => (dashboard?.trend_7d ?? []).map((v, i) => ({ day: `D${i + 1}`, alerts: v })),
    [dashboard]
  );

  const severityData = useMemo(() => {
    const counts: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 };
    for (const a of dashboard?.alerts ?? []) { if (a.severity in counts) counts[a.severity]++; }
    return Object.entries(counts).filter(([, v]) => v > 0).map(([name, value]) => ({ name, value }));
  }, [dashboard]);

  const inviteExpiryLabel = useMemo(() => {
    if (!inviteExpiresAt) return "";
    const rem = new Date(inviteExpiresAt).getTime() - inviteNowMs;
    if (rem <= 0) return "Expired";
    const s = Math.floor(rem / 1000);
    return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m ${s % 60}s`;
  }, [inviteExpiresAt, inviteNowMs]);

  const visibleAlerts = useMemo(
    () => showUnackedOnly ? alertEvents.filter((a) => !a.acknowledged) : alertEvents,
    [alertEvents, showUnackedOnly]
  );

  const topPriorityAlert = useMemo(() => {
    const ordered = [...visibleAlerts].sort((a, b) => {
      const weight = { critical: 4, high: 3, medium: 2, low: 1 } as const;
      const delta = weight[b.risk_level] - weight[a.risk_level];
      if (delta !== 0) return delta;
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
    return ordered[0] ?? null;
  }, [visibleAlerts]);

  const primaryInvestigation = useMemo(() => {
    if (activeCase) {
      const relatedAlert = visibleAlerts.find((alert) => alert.address === activeCase.primary_address) ?? topPriorityAlert;
      return {
        address: activeCase.primary_address,
        chain: (activeCase.primary_chain || "ethereum") as Blockchain,
        riskLevel: activeCase.risk_level,
        score: activeCase.risk_score,
        createdAt: activeCase.created_at,
        explanation: activeCase.summary,
        tags: activeCase.tags,
        relatedAlert,
      };
    }

    const recentAnalysis = analyses[0] ?? null;
    if (!recentAnalysis) return null;
    const relatedAlert = visibleAlerts.find((alert) => alert.address === recentAnalysis.address) ?? topPriorityAlert;
    return {
      address: recentAnalysis.address,
      chain: recentAnalysis.chain,
      riskLevel: recentAnalysis.risk_level,
      score: recentAnalysis.score,
      createdAt: recentAnalysis.created_at,
      explanation: recentAnalysis.explanation,
      tags: recentAnalysis.tags,
      relatedAlert,
    };
  }, [activeCase, analyses, topPriorityAlert, visibleAlerts]);

  const missionHighlights = useMemo(() => {
    return [
      {
        label: "Live Signals",
        value: `${visibleAlerts.filter((alert) => !alert.acknowledged).length}`,
        tone: "text-amber-300",
        detail: "Unacknowledged risk events",
      },
      {
        label: "Active Case",
        value: primaryInvestigation ? `${primaryInvestigation.score}/100` : "—",
        tone: "text-indigo-300",
        detail: primaryInvestigation ? `${primaryInvestigation.chain} · ${primaryInvestigation.riskLevel}` : "No active case yet",
      },
      {
        label: "Team Coverage",
        value: session?.role === "admin" ? `${teamUsers.length || 1}` : `${watchlist.length}`,
        tone: "text-cyan-300",
        detail: session?.role === "admin" ? "Operators in workspace" : "Tracked entities",
      },
    ];
  }, [primaryInvestigation, session?.role, teamUsers.length, visibleAlerts, watchlist.length]);

  const tickerItems = useMemo(() => {
    const items = [
      topPriorityAlert
        ? `PRIORITY · ${topPriorityAlert.chain.toUpperCase()} · ${topPriorityAlert.risk_level.toUpperCase()} · ${topPriorityAlert.address.slice(0, 10)}…`
        : "PRIORITY · No active critical signal",
      primaryInvestigation
        ? `CASE SCORE · ${primaryInvestigation.score}/100 · ${primaryInvestigation.riskLevel.toUpperCase()}`
        : "CASE SCORE · Waiting for first investigation",
      `WATCHLIST · ${watchlist.length} tracked entities`,
      `LIVE ALERTS · ${alertUnread} unread · ${visibleAlerts.length} visible`,
      `TEAM · ${teamUsers.length || (session ? 1 : 0)} operators online`,
    ];
    return items;
  }, [alertUnread, primaryInvestigation, session, teamUsers.length, topPriorityAlert, visibleAlerts.length, watchlist.length]);

  const quickStartChecklist = useMemo(() => {
    const trimmedAddress = walletInput.address.trim();
    return [
      {
        title: "Load a wallet",
        detail: trimmedAddress ? `${walletInput.chain} · ${trimmedAddress.slice(0, 12)}…` : "Paste a wallet address or load one of the sample wallets below.",
        done: Boolean(trimmedAddress),
      },
      {
        title: "Enrich with chain data",
        detail: liveEnrichment
          ? `${liveEnrichment.recent_tx_scanned} recent tx scanned from ${liveEnrichment.source}.`
          : walletInput.chain === "ethereum"
            ? "Use live fill for Ethereum to auto-populate activity, balance, and pricing context."
            : "Non-Ethereum chains currently use analyst-provided context for scoring and workflow.",
        done: Boolean(liveEnrichment),
      },
      {
        title: "Run intelligence",
        detail: intelligence
          ? `${intelligence.risk_level.toUpperCase()} risk · ${intelligence.score}/100 · ${intelligence.fingerprints.length} fingerprints.`
          : "Generate the narrative, action recommendation, and business context for the active wallet.",
        done: Boolean(intelligence),
      },
      {
        title: "Open graph or watchlist",
        detail: showCluster
          ? `${cluster?.nodes.length ?? 0} nodes visualized in the active cluster graph.`
          : "Turn the analysis into action by opening the relationship graph or adding the wallet to the watchlist.",
        done: Boolean(showCluster || watchlist.some((entry) => entry.address === trimmedAddress)),
      },
    ];
  }, [cluster?.nodes.length, intelligence, liveEnrichment, showCluster, walletInput.address, walletInput.chain, watchlist]);

  const hasWorkspaceActivity = useMemo(() => {
    return Boolean(
      analyses.length ||
      cases.length ||
      watchlist.length ||
      visibleAlerts.length ||
      dashboard?.alerts.length ||
      dashboard?.total_wallets_monitored ||
      dashboard?.alerts_today ||
      dashboard?.critical_alerts_today
    );
  }, [analyses.length, cases.length, dashboard?.alerts.length, dashboard?.alerts_today, dashboard?.critical_alerts_today, dashboard?.total_wallets_monitored, visibleAlerts.length, watchlist.length]);

  const seedCaseDraftFromActiveWallet = useCallback(() => {
    const activeAddress = (intelligence?.address ?? walletInput.address).trim();
    const activeChain = intelligence?.chain ?? walletInput.chain;
    const score = intelligence?.score;
    const riskLevel = intelligence?.risk_level;
    const recommendation = intelligence?.narrative.recommended_action_label;

    setCaseForm({
      title: activeAddress ? `Investigate ${activeChain} wallet ${activeAddress.slice(0, 10)}…` : "Investigate flagged wallet",
      summary: intelligence
        ? `${recommendation} · Score ${score}/100 · ${riskLevel?.toUpperCase()} risk. Review wallet behavior, cluster context, and determine escalation path.`
        : "Document why this wallet matters, what triggered the review, and what needs to be decided next.",
      priority: intelligence?.risk_level === "critical" ? "critical" : intelligence?.risk_level === "high" ? "high" : "medium",
      tags: [activeChain, intelligence?.risk_level, "triage"].filter(Boolean).join(", "),
    });
  }, [intelligence, walletInput.address, walletInput.chain]);

  const applyWalletPreset = useCallback((preset: typeof SAMPLE_WALLET_PRESETS[number]) => {
    setWalletInput(preset.walletInput);
    setLiveEnrichment(null);
    setIntelError("");
    setIntelligence(null);
    setCluster(null);
    setShowCluster(false);
    setActiveTab("dashboard");
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const isMetaK = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k";
      if (isMetaK) {
        event.preventDefault();
        setCommandPaletteOpen((open) => !open);
      }
      if (event.key === "Escape") {
        setCommandPaletteOpen(false);
        setCommandQuery("");
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // ─── Auth ──────────────────────────────────────────────────────────────────

  const onLogin = async () => {
    if (!auth.email.trim() || !auth.password.trim()) {
      setAuthError("Enter your email and password.");
      return;
    }

    setIsLoggingIn(true); setAuthError("");
    try {
      await login({ email: auth.email.trim(), password: auth.password });
      setLoggedIn(true);
      const s = getSessionInfo(); setSession(s);
      const [dash, hist] = await Promise.all([getDashboard(), getAnalyses(20)]);
      setDashboard(dash); setAnalyses(hist);
      if (s) await refreshIntelPanels(s.role);
      await refreshCases();
      setAuth({ email: "", password: "" });
    } catch (error) { setAuthError(getErrorMessage(error, "Could not sign in.")); }
    finally { setIsLoggingIn(false); }
  };

  const onAuthSuccess = async () => {
    setLoggedIn(true);
    const s = getSessionInfo();
    setSession(s);
    setSetupStatus({
      status: "ok",
      workspace_ready: true,
      user_count: 1,
      first_signup_becomes_admin: false,
    });
    const [dash, hist] = await Promise.all([getDashboard(), getAnalyses(20)]);
    setDashboard(dash);
    setAnalyses(hist);
    if (s) await refreshIntelPanels(s.role);
    await refreshCases();
  };

  const onCreateCase = async () => {
    if (!caseForm.title.trim() || !caseForm.summary.trim()) {
      setCaseMessage("Case title and summary are required.");
      return;
    }

    setCaseBusy(true);
    setCaseMessage("");
    try {
      const created = await createCase({
        title: caseForm.title.trim(),
        summary: caseForm.summary.trim(),
        priority: caseForm.priority,
        primary_chain: intelligence?.chain ?? walletInput.chain,
        primary_address: (intelligence?.address ?? walletInput.address).trim(),
        risk_score: intelligence?.score ?? topPriorityAlert?.score ?? 0,
        risk_level: intelligence?.risk_level ?? topPriorityAlert?.risk_level ?? "medium",
        source_type: topPriorityAlert ? "alert" : intelligence ? "analysis" : "manual",
        source_ref: topPriorityAlert ? String(topPriorityAlert.id) : intelligence ? String(intelligence.analysis_id) : "",
        tags: caseForm.tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      });
      setCaseForm({ title: "", summary: "", priority: "high", tags: "" });
      setCaseMessage("Case created and investigation workspace updated.");
      setCases((prev) => [created, ...prev.filter((item) => item.id !== created.id)]);
      setSelectedCaseId(created.id);
      setActiveCase(created);
      await refreshCases(created.id);
    } catch {
      setCaseMessage("Could not create case.");
    } finally {
      setCaseBusy(false);
    }
  };

  const onCaseStatusChange = async (status: CaseStatus) => {
    if (!activeCase) return;
    setCaseBusy(true);
    setCaseMessage("");
    try {
      const updated = await updateCase(activeCase.id, { status });
      setActiveCase(updated);
      setCases((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setCaseMessage(`Case moved to ${status.replace("_", " ")}.`);
    } catch {
      setCaseMessage("Could not update case status.");
    } finally {
      setCaseBusy(false);
    }
  };

  const onAddCaseNote = async () => {
    if (!activeCase || !caseNoteForm.body.trim()) return;
    setCaseBusy(true);
    setCaseMessage("");
    try {
      await addCaseNote(activeCase.id, {
        note_type: caseNoteForm.note_type,
        body: caseNoteForm.body.trim(),
        tags: caseNoteForm.tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      });
      setCaseNoteForm({ note_type: "observation", body: "", tags: "" });
      setCaseMessage("Case note captured.");
      await refreshCases(activeCase.id);
    } catch {
      setCaseMessage("Could not save case note.");
    } finally {
      setCaseBusy(false);
    }
  };

  const onAddCaseEntity = async () => {
    if (!activeCase || !caseEntityForm.label.trim() || !caseEntityForm.reference.trim()) return;
    setCaseBusy(true);
    setCaseMessage("");
    try {
      await addCaseEntity(activeCase.id, {
        entity_type: caseEntityForm.entity_type,
        label: caseEntityForm.label.trim(),
        chain: caseEntityForm.chain,
        reference: caseEntityForm.reference.trim(),
        risk_score: intelligence?.score,
        risk_level: intelligence?.risk_level,
      });
      setCaseEntityForm({ entity_type: "wallet", label: "", chain: "ethereum", reference: "" });
      setCaseMessage("Linked entity added to case.");
      await refreshCases(activeCase.id);
    } catch {
      setCaseMessage("Could not link entity.");
    } finally {
      setCaseBusy(false);
    }
  };

  const onAddCaseAttachment = async () => {
    if (!activeCase || !caseAttachmentForm.file_name.trim() || !caseAttachmentForm.file_url.trim()) return;
    setCaseBusy(true);
    setCaseMessage("");
    try {
      await addCaseAttachment(activeCase.id, {
        file_name: caseAttachmentForm.file_name.trim(),
        file_url: caseAttachmentForm.file_url.trim(),
        content_type: caseAttachmentForm.content_type.trim() || "link",
      });
      setCaseAttachmentForm({ file_name: "", file_url: "", content_type: "link" });
      setCaseMessage("Evidence attached to case.");
      await refreshCases(activeCase.id);
    } catch {
      setCaseMessage("Could not add attachment.");
    } finally {
      setCaseBusy(false);
    }
  };

  const onSignupEmail = async () => {
    if (!signupForm.email.trim() || !signupForm.password.trim()) {
      setSignupMessage("Work email and password are required.");
      return;
    }
    if (!signupForm.email.includes("@")) {
      setSignupMessage("Enter a valid email address.");
      return;
    }
    if (signupForm.password.length < 8) {
      setSignupMessage("Password must be at least 8 characters.");
      return;
    }
    if (signupForm.password !== signupForm.confirmPassword) {
      setSignupMessage("Passwords do not match.");
      return;
    }
    setSignupBusy(true);
    setSignupMessage("");
    setDemoCodeHint("");
    try {
      await signupWithEmail({ email: signupForm.email.trim(), password: signupForm.password, role: "analyst" });
      setSetupStatus({
        status: "ok",
        workspace_ready: true,
        user_count: 1,
        first_signup_becomes_admin: false,
      });
      setSignupForm({ email: "", password: "", confirmPassword: "", phone: "", code: "" });
      setSignupMessage("Workspace created. You are signed in.");
      await onAuthSuccess();
    } catch (error) {
      setSignupMessage(getErrorMessage(error, "Could not create your workspace."));
    } finally {
      setSignupBusy(false);
    }
  };

  const onSocialSignup = async (provider: "Google" | "Apple") => {
    if (!signupForm.email.trim()) {
      setSignupMessage("Enter your work email before starting the SSO preview flow.");
      return;
    }
    setSignupBusy(true);
    setSignupMessage("");
    try {
      const resp = await signupWithOAuth({ provider: provider.toLowerCase() as "google" | "apple", email: signupForm.email.trim() });
      setSignupMessage(`${provider} preview is ready. ${resp.message}`);
    } catch (error) {
      setSignupMessage(getErrorMessage(error, `${provider} SSO preview setup failed.`));
    } finally {
      setSignupBusy(false);
    }
  };

  const onPhoneStart = async () => {
    if (!signupForm.phone.trim()) {
      setSignupMessage("Enter a phone number before requesting a preview code.");
      return;
    }
    setSignupBusy(true);
    setSignupMessage("");
    setDemoCodeHint("");
    try {
      const resp = await startPhoneSignup({ phone: signupForm.phone.trim() });
      setDemoCodeHint(resp.code_hint);
      setSignupMessage("Preview phone code generated. Use the hint below to complete the preview flow.");
    } catch (error) {
      setSignupMessage(getErrorMessage(error, "Could not generate a preview phone code."));
    } finally {
      setSignupBusy(false);
    }
  };

  const onPhoneVerify = async () => {
    if (!signupForm.phone.trim() || !signupForm.code.trim()) {
      setSignupMessage("Phone and verification code are required.");
      return;
    }
    setSignupBusy(true);
    setSignupMessage("");
    try {
      await verifyPhoneSignup({ phone: signupForm.phone.trim(), code: signupForm.code.trim() });
      setSignupForm({ email: "", password: "", confirmPassword: "", phone: "", code: "" });
      setDemoCodeHint("");
      setSignupMessage("Preview phone verification worked. You are signed in.");
      await onAuthSuccess();
    } catch (error) {
      setSignupMessage(getErrorMessage(error, "Preview phone verification failed."));
    } finally {
      setSignupBusy(false);
    }
  };

  const onLogout = async () => {
    clearAuthToken(); setLoggedIn(false); setSession(null);
    setAuditLogs([]); setTeamUsers([]); setInvites([]); setLastAdminRefreshAt("");
    setAlertEvents([]); setAlertUnread(0); setWatchlist([]); setWebhooks([]);
    const [dash, hist] = await Promise.all([getDashboard(), getAnalyses(20)]);
    setDashboard(dash); setAnalyses(hist);
  };

  const onChangePassword = async () => {
    if (!passwordForm.current_password || !passwordForm.new_password) { setPasswordMessage("Both passwords required."); return; }
    setPasswordBusy(true); setPasswordMessage("");
    try {
      await changePassword(passwordForm);
      setPasswordMessage("Password updated.");
      setPasswordForm({ current_password: "", new_password: "" });
    } catch { setPasswordMessage("Password update failed."); }
    finally { setPasswordBusy(false); }
  };

  // ─── Team / Invites ────────────────────────────────────────────────────────

  const onCreateTeamUser = async () => {
    if (!teamForm.email || !teamForm.password) { setTeamError("Email and password required."); return; }
    setTeamBusy(true); setTeamError("");
    try {
      await createTeamUser(teamForm);
      const [users, logs] = await Promise.all([getTeamUsers(), getAuditLogs(8)]);
      setTeamUsers(users); setAuditLogs(logs);
      setTeamForm({ email: "", password: "", role: "analyst" });
    } catch { setTeamError("Could not create user."); }
    finally { setTeamBusy(false); }
  };

  const onCreateInvite = async () => {
    if (!inviteEmail) { setInviteError("Email required."); return; }
    setInviteBusy(true); setInviteError(""); setInviteCopied("");
    try {
      const inv = await createInvite({ email: inviteEmail, role: inviteRole });
      setInviteToken(inv.token); setInviteExpiresAt(inv.expires_at);
      if (typeof window !== "undefined")
        setInviteLink(`${window.location.origin}/invite?token=${encodeURIComponent(inv.token)}`);
      const [logs, pending] = await Promise.all([getAuditLogs(8), getInvites(15)]);
      setAuditLogs(logs); setInvites(pending); setLastAdminRefreshAt(new Date().toISOString()); setInviteEmail("");
    } catch { setInviteError("Could not create invite."); }
    finally { setInviteBusy(false); }
  };

  const onRefreshInvites = async () => {
    setInviteListBusy(true); setInviteActionMessage("");
    try { setInvites(await getInvites(15)); setLastAdminRefreshAt(new Date().toISOString()); }
    catch { setInviteActionMessage("Unable to refresh invites."); }
    finally { setInviteListBusy(false); }
  };

  const onRevokeInvite = async (token: string) => {
    setRevokingToken(token); setInviteActionMessage("");
    try {
      const r = await revokeInvite(token);
      setInviteActionMessage(r.revoked ? "Invite revoked." : "Could not revoke.");
      const [items, logs] = await Promise.all([getInvites(15), getAuditLogs(8)]);
      setInvites(items); setAuditLogs(logs); setLastAdminRefreshAt(new Date().toISOString());
    } catch { setInviteActionMessage("Revoke failed."); }
    finally { setRevokingToken(""); }
  };

  const onCopyInviteLink = async () => {
    if (!inviteLink) return;
    try { await navigator.clipboard.writeText(inviteLink); setInviteCopied("Copied!"); window.setTimeout(() => setInviteCopied(""), 2500); }
    catch { setInviteCopied("Copy failed."); }
  };

  // ─── Intelligence ──────────────────────────────────────────────────────────

  const onAnalyze = async () => {
    setLoadingIntel(true); setIntelError(""); setIntelligence(null); setCluster(null); setShowCluster(false);
    try {
      const result = await analyzeWalletIntelligence(walletInput);
      setIntelligence(result);
      const [hist, alerts] = await Promise.all([getAnalyses(20), getAlertEvents(50)]);
      setAnalyses(hist); setAlertEvents(alerts.items); setAlertUnread(alerts.unread_count);
    } catch (e) { setIntelError(e instanceof Error ? e.message : "Analysis failed"); }
    finally { setLoadingIntel(false); }
  };

  const onEnrichWalletLive = async () => {
    const trimmedAddress = walletInput.address.trim();
    if (!trimmedAddress) {
      setIntelError("Enter a wallet address first");
      return;
    }

    setLoadingEnrich(true);
    setIntelError("");
    try {
      const enriched = await enrichWalletInput(trimmedAddress, walletInput.chain);
      setIntelligence(null);
      setCluster(null);
      setShowCluster(false);
      setWalletInput({
        chain: enriched.chain,
        address: enriched.address,
        txn_24h: enriched.txn_24h,
        volume_24h_usd: enriched.volume_24h_usd,
        sanctions_exposure_pct: enriched.sanctions_exposure_pct,
        mixer_exposure_pct: enriched.mixer_exposure_pct,
        bridge_hops: enriched.bridge_hops,
      });
      setLiveEnrichment(enriched);
    } catch (e) {
      setIntelError(e instanceof Error ? e.message : "Live enrichment failed");
    } finally {
      setLoadingEnrich(false);
    }
  };

  const loadClusterData = useCallback(async (showPanel = false, quiet = false) => {
    const trimmedAddress = walletInput.address.trim();
    if (!trimmedAddress) return;
    if (!quiet) setLoadingCluster(true);
    try {
      const c = await getWalletCluster(trimmedAddress, walletInput.chain, {
        txn_24h: walletInput.txn_24h,
        volume_24h_usd: walletInput.volume_24h_usd,
        sanctions_exposure_pct: walletInput.sanctions_exposure_pct,
        mixer_exposure_pct: walletInput.mixer_exposure_pct,
        bridge_hops: walletInput.bridge_hops,
      });
      setCluster(c);
      if (showPanel) setShowCluster(true);
    } catch { /* silent */ }
    finally { if (!quiet) setLoadingCluster(false); }
  }, [walletInput]);

  const onLoadCluster = async () => {
    await loadClusterData(true, false);
  };

  useEffect(() => {
    if (!showCluster || !cluster || !intelligence) return;

    const refreshMs = Math.max(10_000, cluster.refresh_suggested_after_sec * 1000);
    const timer = window.setTimeout(() => {
      void loadClusterData(false, true);
    }, refreshMs);

    return () => window.clearTimeout(timer);
  }, [showCluster, cluster, intelligence, loadClusterData]);

  const onAddTag = async (analysisId: number, tag: string) => {
    if (!tag.trim()) return;
    const current = analyses.find((a) => a.id === analysisId);
    if (!current) return;
    const newTags = [...new Set([...current.tags, tag.trim()])];
    setTagBusy(true); setTagMessage("");
    try {
      const updated = await updateAnalysisTags(analysisId, newTags);
      setAnalyses((prev) => prev.map((a) => (a.id === analysisId ? updated : a)));
      setTagInput(""); setTagMessage("Tag added."); window.setTimeout(() => setTagMessage(""), 2000);
    } catch { setTagMessage("Failed to add tag."); }
    finally { setTagBusy(false); }
  };

  const onRemoveTag = async (analysisId: number, tag: string) => {
    const current = analyses.find((a) => a.id === analysisId);
    if (!current) return;
    setTagBusy(true);
    try {
      const updated = await updateAnalysisTags(analysisId, current.tags.filter((t) => t !== tag));
      setAnalyses((prev) => prev.map((a) => (a.id === analysisId ? updated : a)));
    } catch { setTagMessage("Failed to remove tag."); }
    finally { setTagBusy(false); }
  };

  const onExportCSV = async () => {
    setCsvBusy(true); setCsvMessage("");
    try { await exportAnalysesCSV(500); setCsvMessage("Downloaded."); window.setTimeout(() => setCsvMessage(""), 3000); }
    catch { setCsvMessage("Export failed."); }
    finally { setCsvBusy(false); }
  };

  // ─── Watchlist ─────────────────────────────────────────────────────────────

  const onAddWatchlist = async () => {
    if (!watchForm.address.trim() || !watchForm.label.trim()) { setWatchlistError("Address and label required."); return; }
    setWatchlistBusy(true); setWatchlistError("");
    try {
      await addToWatchlist({ chain: watchForm.chain, address: watchForm.address.trim(), label: watchForm.label.trim(), alert_on_activity: true });
      setWatchlist(await getWatchlist());
      setWatchForm({ address: "", label: "", chain: "ethereum" });
    } catch (e) {
      setWatchlistError(e instanceof Error && e.message.includes("409") ? "Already on watchlist." : "Failed to add.");
    } finally { setWatchlistBusy(false); }
  };

  const onRemoveWatchlist = async (id: number) => {
    setWatchlistBusy(true);
    try { await removeFromWatchlist(id); setWatchlist((prev) => prev.filter((w) => w.id !== id)); }
    catch { /* silent */ }
    finally { setWatchlistBusy(false); }
  };

  const onQuickWatch = async () => {
    if (!intelligence) return;
    setWatchlistBusy(true);
    try {
      await addToWatchlist({ chain: intelligence.chain, address: intelligence.address, label: `Flagged ${intelligence.risk_level}`, alert_on_activity: true });
      setWatchlist(await getWatchlist());
    } catch { /* already watched */ }
    finally { setWatchlistBusy(false); }
  };

  // ─── Alerts ────────────────────────────────────────────────────────────────

  const onAckAlert = async (id: number) => {
    setAlertBusy(true);
    try {
      await acknowledgeAlert(id);
      setAlertEvents((prev) => prev.map((a) => a.id === id ? { ...a, acknowledged: true } : a));
      setAlertUnread((n) => Math.max(0, n - 1));
    } catch { /* silent */ }
    finally { setAlertBusy(false); }
  };

  const onAckAll = async () => {
    setAlertBusy(true);
    try {
      await Promise.all(alertEvents.filter((a) => !a.acknowledged).map((a) => acknowledgeAlert(a.id)));
      setAlertEvents((prev) => prev.map((a) => ({ ...a, acknowledged: true })));
      setAlertUnread(0);
    } catch { /* silent */ }
    finally { setAlertBusy(false); }
  };

  // ─── Alerts v2 ────────────────────────────────────────────────────────────

  const refreshAlertsV2 = useCallback(async () => {
    setAlertsV2Loading(true);
    setAlertsV2Error("");
    try {
      const result = await getAlerts({
        ...(alertsV2Filter.severity ? { severity: alertsV2Filter.severity as AlertSeverity } : {}),
        ...(alertsV2Filter.alert_type ? { alert_type: alertsV2Filter.alert_type as AlertType } : {}),
        ...(alertsV2Filter.unacked_only ? { unacked_only: true } : {}),
        limit: 100,
      });
      setAlertsV2(result.items);
      setAlertsV2Unread(result.unread_count);
    } catch {
      setAlertsV2Error("Could not load alerts.");
    } finally {
      setAlertsV2Loading(false);
    }
  }, [alertsV2Filter]);

  const onAckAlertV2Handler = async (id: number) => {
    try {
      await ackAlertV2(id);
      setAlertsV2((prev) =>
        prev.map((a) => a.id === id ? { ...a, acknowledged: true, acknowledged_at: new Date().toISOString() } : a)
      );
      setAlertsV2Unread((n) => Math.max(0, n - 1));
    } catch { /* silent */ }
  };

  const onAckAllAlertsV2Handler = async () => {
    setAlertsV2Loading(true);
    try {
      await ackAllAlertsV2();
      setAlertsV2((prev) =>
        prev.map((a) => ({ ...a, acknowledged: true, acknowledged_at: a.acknowledged_at ?? new Date().toISOString() }))
      );
      setAlertsV2Unread(0);
    } catch { /* silent */ }
    finally { setAlertsV2Loading(false); }
  };

  const onResolveAlertHandler = async (id: number) => {
    try {
      const updated = await resolveAlert(id, { resolved: true });
      setAlertsV2((prev) => prev.map((a) => a.id === id ? updated : a));
    } catch { /* silent */ }
  };

  const onCreateManualAlert = async () => {
    if (!manualAlertForm.title.trim() || !manualAlertForm.address.trim()) {
      setAlertsV2Message("Title and address are required.");
      return;
    }
    setManualAlertBusy(true);
    setAlertsV2Message("");
    try {
      await createAlertManual({
        alert_type: manualAlertForm.alert_type,
        severity: manualAlertForm.severity,
        chain: manualAlertForm.chain,
        address: manualAlertForm.address.trim(),
        score: manualAlertForm.score,
        risk_level: manualAlertForm.severity === "critical" ? "critical"
          : manualAlertForm.severity === "high" ? "high"
          : manualAlertForm.severity === "warning" ? "medium"
          : "low",
        title: manualAlertForm.title.trim(),
        body: manualAlertForm.body.trim(),
      });
      setManualAlertForm({ title: "", body: "", severity: "high", alert_type: "manual", chain: "ethereum", address: "", score: 70 });
      setAlertsV2Message("Alert created.");
      await refreshAlertsV2();
    } catch {
      setAlertsV2Message("Could not create alert.");
    } finally {
      setManualAlertBusy(false);
    }
  };

  // ─── Incidents ─────────────────────────────────────────────────────────────

  const refreshIncidents = useCallback(async (preferredId?: number | null) => {
    setIncidentsLoading(true);
    setIncidentError("");
    try {
      const result = await getIncidents({
        limit: 50,
        ...(incidentStatusFilter !== "all" ? { status: incidentStatusFilter as IncidentStatus } : {}),
      });
      setIncidents(result.items);
      const nextId = preferredId ?? result.items[0]?.id ?? null;
      setSelectedIncidentId(nextId);
      if (nextId) {
        const detail = await getIncidentDetail(nextId);
        setActiveIncident(detail);
      } else {
        setActiveIncident(null);
      }
    } catch {
      setIncidentError("Could not load incidents.");
    } finally {
      setIncidentsLoading(false);
    }
  }, [incidentStatusFilter]);

  const onCreateIncidentHandler = async () => {
    if (!incidentForm.title.trim() || !incidentForm.description.trim()) {
      setIncidentMessage("Title and description are required.");
      return;
    }
    setIncidentBusy(true);
    setIncidentMessage("");
    try {
      const created = await createIncident({
        title: incidentForm.title.trim(),
        description: incidentForm.description.trim(),
        severity: incidentForm.severity,
      });
      setIncidentForm({ title: "", description: "", severity: "high" });
      setIncidentMessage("Incident created.");
      await refreshIncidents(created.id);
    } catch {
      setIncidentMessage("Could not create incident.");
    } finally {
      setIncidentBusy(false);
    }
  };

  const onUpdateIncidentStatus = async (status: IncidentStatus) => {
    if (!activeIncident) return;
    setIncidentBusy(true);
    try {
      const updated = await updateIncident(activeIncident.id, { status });
      setActiveIncident(updated);
      setIncidents((prev) => prev.map((i) => i.id === updated.id ? updated : i));
      setIncidentMessage(`Incident moved to ${status}.`);
    } catch {
      setIncidentMessage("Could not update incident.");
    } finally {
      setIncidentBusy(false);
    }
  };

  // ─── Tab-load effects ──────────────────────────────────────────────────────

  useEffect(() => {
    if (activeTab === "alerts" && loggedIn) void refreshAlertsV2();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, loggedIn]);

  useEffect(() => {
    if (activeTab === "incidents" && loggedIn) void refreshIncidents();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, loggedIn, incidentStatusFilter]);

  // ─── Webhooks ──────────────────────────────────────────────────────────────

  const onCreateWebhook = async () => {
    if (!webhookUrl.trim()) { setWebhookError("URL required."); return; }
    setWebhookBusy(true); setWebhookError("");
    try {
      await createWebhook({ url: webhookUrl.trim(), events: webhookEvents });
      setWebhooks(await getWebhooks()); setWebhookUrl("");
    } catch { setWebhookError("Failed to create webhook."); }
    finally { setWebhookBusy(false); }
  };

  const onDeleteWebhook = async (id: number) => {
    setWebhookBusy(true);
    try { await deleteWebhook(id); setWebhooks((prev) => prev.filter((w) => w.id !== id)); }
    catch { /* silent */ }
    finally { setWebhookBusy(false); }
  };

  const canLoadCluster = walletInput.address.trim().length > 0;
  const previewAuthEnabled = PREVIEW_AUTH_ENABLED;
  const isFirstWorkspaceOwnerFlow = !loggedIn && Boolean(setupStatus?.first_signup_becomes_admin);
  const clusterActionLabel = walletInput.chain === "ethereum"
    ? (loadingCluster ? "Loading live graph" : showCluster ? "Refresh live cluster" : "Open live cluster")
    : (loadingCluster ? "Loading graph" : showCluster ? "Refresh cluster" : "Open relationship graph");

  const commandItems = [
    { label: "Run intelligence", action: () => void onAnalyze(), enabled: session?.role !== "viewer" },
    { label: clusterActionLabel, action: () => void onLoadCluster(), enabled: canLoadCluster },
    { label: "Add active wallet to watchlist", action: () => void onQuickWatch(), enabled: Boolean(intelligence && session?.role !== "viewer") },
    { label: "Acknowledge all alerts", action: () => void onAckAll(), enabled: alertUnread > 0 && session?.role !== "viewer" },
    { label: csvBusy ? "Exporting intelligence" : "Export intelligence CSV", action: () => void onExportCSV(), enabled: session?.role !== "viewer" },
    { label: "Refresh admin operations", action: () => void onRefreshInvites(), enabled: session?.role === "admin" },
  ].filter((item) => item.enabled && item.label.toLowerCase().includes(commandQuery.toLowerCase()));

  const deskHeadline = primaryInvestigation
    ? `Focus on ${primaryInvestigation.chain} risk without losing the audit trail.`
    : topPriorityAlert
      ? `A live ${topPriorityAlert.risk_level} signal is ready for analyst review.`
      : "Your operating desk is ready for the next wallet decision.";

  const deskNarrative = primaryInvestigation
    ? primaryInvestigation.explanation
    : topPriorityAlert?.body ?? "Load a sample wallet or paste a live address to move from enrichment to monitoring and documented escalation in one flow.";

  const deskNextAction = primaryInvestigation
    ? "Open the active investigation, review the relationship graph, and decide whether the wallet belongs on the watchlist or in an incident."
    : topPriorityAlert
      ? "Triage the top alert, acknowledge the queue if understood, or open a case if the signal needs documented escalation."
      : "Start with a validated wallet, run live enrichment, then turn the result into monitoring or a case if the evidence warrants it.";

  const intakeAddress = walletInput.address.trim();
  const currentWalletTracked = intakeAddress.length > 0 && watchlist.some((entry) => entry.address === intakeAddress);
  const walletBrief = intakeAddress
    ? `${walletInput.chain} · ${intakeAddress.slice(0, 10)}…${intakeAddress.slice(-6)}`
    : "No wallet loaded";
  const investigationNextMove = intelligence
    ? showCluster
      ? "Graph is open. Decide whether to watch the wallet, create a case, or link counterparties into an investigation."
      : currentWalletTracked
        ? "This wallet is already monitored. Open the cluster or create a case if the narrative needs durable review."
        : "Intelligence is ready. Open the relationship graph or put the wallet on the watchlist before escalating further."
    : liveEnrichment
      ? "Chain context is loaded. Run intelligence next to generate the narrative, score, and recommended action."
      : walletInput.chain === "ethereum"
        ? "Start with live fill for Ethereum, then run intelligence to generate the analyst narrative."
        : "Paste analyst context for this chain, then run intelligence to produce a decision-ready explanation.";
    const deskResponseWindow = primaryInvestigation?.createdAt ?? topPriorityAlert?.created_at ?? null;
    const operatorBriefItems = [
      {
        label: "Desk status",
        value: topPriorityAlert
          ? `${topPriorityAlert.risk_level.toUpperCase()} signal live`
          : primaryInvestigation
            ? "Active investigation open"
            : "Desk ready for intake",
        detail: alertUnread > 0
          ? `${alertUnread} unread signals still need analyst acknowledgement.`
          : "No unread queue pressure at the moment.",
        tone: topPriorityAlert
          ? "border-amber-500/20 bg-amber-500/10 text-amber-100"
          : primaryInvestigation
            ? "border-indigo-500/20 bg-indigo-500/10 text-indigo-100"
            : "border-emerald-500/20 bg-emerald-500/10 text-emerald-100",
      },
      {
        label: "Primary target",
        value: primaryInvestigation
          ? `${primaryInvestigation.chain} · ${primaryInvestigation.address.slice(0, 10)}…`
          : topPriorityAlert
            ? `${topPriorityAlert.chain} · ${topPriorityAlert.address.slice(0, 10)}…`
            : walletBrief,
        detail: primaryInvestigation
          ? `${primaryInvestigation.score}/100 risk score with ${primaryInvestigation.riskLevel} severity.`
          : topPriorityAlert
            ? "Escalate the live signal if it needs durable case tracking."
            : "Load a wallet to create a concrete target for triage.",
        tone: "border-slate-800/80 bg-slate-950/40 text-white",
      },
      {
        label: "Response window",
        value: deskResponseWindow
          ? formatDistanceToNow(new Date(deskResponseWindow), { addSuffix: true })
          : "No active timer",
        detail: primaryInvestigation ? deskNextAction : investigationNextMove,
        tone: "border-cyan-500/20 bg-cyan-500/10 text-cyan-100",
      },
    ];

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="premium-shell min-h-screen grid-bg">
      <main className="relative z-10 mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {loggedIn && (
          <aside className={cn("command-rail fixed right-4 top-32 z-20 hidden xl:block", commandRailCollapsed ? "command-rail-collapsed" : "command-rail-open")}>
            <div className="command-rail-inner">
              <div className="mb-3 flex items-center justify-between gap-2">
                {!commandRailCollapsed && <p className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Quick ops</p>}
                <button onClick={() => setCommandRailCollapsed((v) => !v)} className="rounded-lg border border-slate-800 bg-slate-950/60 p-2 text-slate-400 hover:text-white">
                  {commandRailCollapsed ? <PanelRightOpen className="h-3.5 w-3.5" /> : <PanelRightClose className="h-3.5 w-3.5" />}
                </button>
              </div>
              <div className="space-y-2">
                {commandItems.slice(0, 5).map((item) => (
                  <button key={item.label} onClick={item.action} className={cn("rail-action", commandRailCollapsed && "rail-action-collapsed")} title={item.label}>
                    <Zap className="h-3.5 w-3.5 shrink-0" />
                    {!commandRailCollapsed && <span>{item.label}</span>}
                  </button>
                ))}
              </div>
            </div>
          </aside>
        )}

        {/* Header */}
        {/* ── Top Navigation ───────────────────────────────────────────────── */}
        <header className="mb-10 space-y-5">
          <nav className="workspace-nav flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            {/* Brand */}
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/30">
                <ShieldCheck className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="text-base font-bold tracking-tight text-white leading-none">Compliance Copilot</p>
                <p className="text-[11px] text-slate-400 leading-none mt-0.5">Risk Intelligence Platform</p>
              </div>
            </div>

            {/* Right side */}
            <div className="flex flex-wrap items-center gap-2.5">
              {loggedIn && (
                <div className="rounded-full border border-cyan-500/25 bg-cyan-500/10 px-3 py-1.5 text-[11px] font-medium text-cyan-100">
                  {primaryInvestigation ? `Active focus · ${primaryInvestigation.chain} ${primaryInvestigation.riskLevel}` : "Workspace live"}
                </div>
              )}
              {alertUnread > 0 && (
                <div className="flex items-center gap-1.5 rounded-full border border-rose-500/40 bg-rose-500/10 px-3 py-1.5">
                  <Bell className="h-3.5 w-3.5 text-rose-300" />
                  <span className="text-xs font-semibold text-rose-200">{alertUnread} unread</span>
                </div>
              )}
              {loggedIn && session ? (
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-2 rounded-full border border-slate-700/80 bg-slate-900/70 px-3 py-1.5 text-xs">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-[10px] font-bold text-white">
                      {session.email[0].toUpperCase()}
                    </span>
                    <span className="max-w-[140px] truncate text-slate-300">{session.email}</span>
                    <span className={cn(
                      "rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide",
                      session.role === "admin"   && "bg-violet-500/25 text-violet-300",
                      session.role === "analyst" && "bg-indigo-500/20 text-indigo-300",
                      session.role === "viewer"  && "bg-slate-700/60 text-slate-400",
                    )}>
                      {session.role}
                    </span>
                  </div>
                  <button
                    onClick={onLogout}
                    className="flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-400 transition hover:border-rose-500/50 hover:text-rose-300 active:scale-95"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    Sign out
                  </button>
                </div>
              ) : !loggedIn ? (
                <div className="flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-500">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                  Secure workspace
                </div>
              ) : null}
            </div>
          </nav>

          {loggedIn && (
            <div className="ticker-shell mb-4 overflow-hidden rounded-2xl">
              <div className="ticker-track">
                {[...tickerItems, ...tickerItems].map((item, index) => (
                  <span key={`${item}-${index}`} className="ticker-item">{item}</span>
                ))}
              </div>
            </div>
          )}

          {loggedIn && (
            <div className="workspace-toolbar flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div className="space-y-3">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Workspace navigation</p>
                  <p className="mt-1 text-xs text-slate-400">Move between the live desk, the alert queue, and active incidents without losing context.</p>
                </div>
                <div className="terminal-tabs">
                  <button onClick={() => setActiveTab("dashboard")} className={cn("terminal-tab", activeTab === "dashboard" && "terminal-tab-active")}>Dashboard</button>
                  <button onClick={() => { setActiveTab("alerts"); }} className={cn("terminal-tab inline-flex items-center gap-1.5", activeTab === "alerts" && "terminal-tab-active")}>
                    Alerts
                    {alertsV2Unread > 0 && <span className="rounded-full bg-rose-500 px-1.5 py-0.5 text-[9px] font-bold leading-none text-white">{alertsV2Unread}</span>}
                  </button>
                  <button onClick={() => { setActiveTab("incidents"); }} className={cn("terminal-tab inline-flex items-center gap-1.5", activeTab === "incidents" && "terminal-tab-active")}>
                    Incidents
                    {incidents.filter((i) => i.status === "open" || i.status === "investigating").length > 0 && (
                      <span className="rounded-full bg-orange-500 px-1.5 py-0.5 text-[9px] font-bold leading-none text-white">
                        {incidents.filter((i) => i.status === "open" || i.status === "investigating").length}
                      </span>
                    )}
                  </button>
                  <button onClick={() => setActiveTab("dashboard")} className={cn("terminal-tab", activeTab === "dashboard" && "terminal-tab-active")}>Intelligence</button>
                  <button onClick={() => setActiveTab("dashboard")} className={cn("terminal-tab", activeTab === "dashboard" && "terminal-tab-active")}>Investigations</button>
                  {session?.role === "admin" && <button onClick={() => setActiveTab("dashboard")} className={cn("terminal-tab", activeTab === "dashboard" && "terminal-tab-active")}>Admin</button>}
                </div>
              </div>
              <div className="flex flex-wrap gap-2 xl:max-w-[30rem] xl:justify-end">
                <button onClick={() => setCommandPaletteOpen(true)} className="command-chip inline-flex items-center gap-2">
                  <Search className="h-3.5 w-3.5" />
                  Command Palette
                  <span className="rounded-md border border-slate-700 px-1.5 py-0.5 text-[10px] text-slate-500">⌘K</span>
                </button>
                <button onClick={onAckAll} disabled={alertBusy || alertUnread === 0 || session?.role === "viewer"} className="command-chip disabled:opacity-50">
                  Clear alerts
                </button>
                <button onClick={onLoadCluster} disabled={!canLoadCluster || loadingCluster} className="command-chip disabled:opacity-50">
                  {walletInput.chain === "ethereum"
                    ? (loadingCluster ? "Loading live graph…" : "Open live cluster")
                    : (loadingCluster ? "Loading graph…" : "Open graph")}
                </button>
                <button onClick={onExportCSV} disabled={csvBusy || session?.role === "viewer"} className="command-chip disabled:opacity-50">
                  {csvBusy ? "Exporting…" : "Export intelligence"}
                </button>
                {session?.role === "admin" && (
                  <button onClick={onRefreshInvites} disabled={inviteListBusy} className="command-chip disabled:opacity-50">
                    {inviteListBusy ? "Refreshing…" : "Refresh admin ops"}
                  </button>
                )}
                <button onClick={() => setCommandRailCollapsed((v) => !v)} className="command-chip inline-flex items-center gap-2">
                  {commandRailCollapsed ? <PanelRightOpen className="h-3.5 w-3.5" /> : <PanelRightClose className="h-3.5 w-3.5" />}
                  {commandRailCollapsed ? "Expand rail" : "Collapse rail"}
                </button>
              </div>
            </div>
          )}

          {/* ── Login card — only when signed out ────────────────────────── */}
          {!loggedIn && (
            <div className="space-y-6 animate-fade-in-up">
              <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
                <article className="glass relative overflow-hidden rounded-3xl p-7">
                <span className="hero-orb hero-orb-indigo" />
                <span className="hero-orb hero-orb-cyan" />
                <div className="relative z-10 space-y-5">
                  <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/35 bg-indigo-500/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-indigo-300">
                    <Sparkles className="h-3.5 w-3.5" />
                    Compliance operations for crypto teams
                  </div>
                  <div>
                    <h2 className="text-3xl font-bold leading-tight text-white sm:text-4xl">Know what a wallet means, not just what it touched.</h2>
                    <p className="mt-3 max-w-xl text-sm leading-relaxed text-slate-300">
                      Compliance Copilot gives operations, AML, and VIP-risk teams one screen to enrich wallets, score behavior, open investigations, and keep a defensible audit trail when money is about to move.
                    </p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-2xl border border-slate-700/70 bg-slate-950/40 p-3">
                      <p className="text-2xl font-bold text-white">1 desk</p>
                      <p className="text-[11px] text-slate-500">Intelligence, watchlist, incidents, and cases together</p>
                    </div>
                    <div className="rounded-2xl border border-slate-700/70 bg-slate-950/40 p-3">
                      <p className="text-2xl font-bold text-white">Live</p>
                      <p className="text-[11px] text-slate-500">Ethereum enrichment and counterparty clustering</p>
                    </div>
                    <div className="rounded-2xl border border-slate-700/70 bg-slate-950/40 p-3">
                      <p className="text-2xl font-bold text-white">Actionable</p>
                      <p className="text-[11px] text-slate-500">From recommendation to watchlist and case handoff</p>
                    </div>
                  </div>
                  <div className="grid gap-3 lg:grid-cols-[1.05fr_.95fr]">
                    <div className="rounded-2xl border border-slate-700/70 bg-slate-950/40 p-4">
                      <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">What it does</p>
                      <div className="mt-3 space-y-3 text-xs text-slate-300">
                        <div className="flex items-start gap-3">
                          <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-indigo-300" />
                          <p>Explains wallet behavior with risk score, fingerprints, narrative, and recommended response.</p>
                        </div>
                        <div className="flex items-start gap-3">
                          <Globe className="mt-0.5 h-3.5 w-3.5 shrink-0 text-cyan-300" />
                          <p>Shows relationship graphs so investigators can see counterparties instead of guessing from raw transactions.</p>
                        </div>
                        <div className="flex items-start gap-3">
                          <Bell className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300" />
                          <p>Turns important wallets into persistent monitoring with alerts, incidents, and case workflows.</p>
                        </div>
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-700/70 bg-slate-950/40 p-4">
                      <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">How teams use it</p>
                      <div className="mt-3 space-y-3 text-xs text-slate-300">
                        <div className="onboarding-step">
                          <span className="onboarding-step-index">1</span>
                          <div>
                            <p className="font-medium text-white">Paste a wallet</p>
                            <p className="text-slate-400">Bring in a client deposit, treasury counterparty, VIP sender, or suspicious address.</p>
                          </div>
                        </div>
                        <div className="onboarding-step">
                          <span className="onboarding-step-index">2</span>
                          <div>
                            <p className="font-medium text-white">Generate intelligence</p>
                            <p className="text-slate-400">Auto-fill Ethereum context or add analyst context for other chains, then score the wallet.</p>
                          </div>
                        </div>
                        <div className="onboarding-step">
                          <span className="onboarding-step-index">3</span>
                          <div>
                            <p className="font-medium text-white">Escalate only when needed</p>
                            <p className="text-slate-400">Open a cluster graph, create an incident, or document a case without leaving the desk.</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </article>

              <article className="glass rounded-3xl p-6 animate-scale-in">
                {isFirstWorkspaceOwnerFlow && (
                  <div className="mb-4 rounded-2xl border border-cyan-500/25 bg-cyan-500/10 px-4 py-3 text-xs text-cyan-100">
                    <p className="font-semibold text-cyan-50">First-run workspace setup</p>
                    <p className="mt-1">No operators exist yet. The first email signup creates the workspace owner account so you can invite analysts after launch.</p>
                  </div>
                )}
                <div className="mb-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/8 px-4 py-3 text-xs text-emerald-100">
                  Best for exchanges, OTC desks, PSPs, treasury teams, and VIP risk operators who need to explain a wallet decision fast.
                </div>
                <div className="mb-5 flex rounded-xl border border-slate-700 bg-slate-900/60 p-1">
                  <button
                    onClick={() => { setAuthMode("signin"); setSignupMessage(""); setDemoCodeHint(""); setAuthError(""); }}
                    className={cn("flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition", authMode === "signin" ? "bg-indigo-500 text-white" : "text-slate-400 hover:text-slate-200")}
                  >
                    Sign in
                  </button>
                  <button
                    onClick={() => { setAuthMode("signup"); setAuthError(""); setSignupMessage(""); setDemoCodeHint(""); }}
                    className={cn("flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition", authMode === "signup" ? "bg-violet-500 text-white" : "text-slate-400 hover:text-slate-200")}
                  >
                    Sign up
                  </button>
                </div>

                {authMode === "signin" ? (
                  <div className="space-y-3.5">
                    <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/8 px-3 py-3 text-[11px] text-indigo-100">
                      {previewAuthEnabled
                        ? "Email and password is the primary sign-in path today. Optional preview auth methods stay clearly separated until full provider integrations are connected."
                        : "Email and password is the primary sign-in path today for operators, analysts, and compliance reviewers."}
                    </div>
                    <div>
                      <label className="mb-1.5 block text-xs font-medium text-slate-400">Email</label>
                      <input
                        value={auth.email}
                        onChange={(e) => setAuth((s) => ({ ...s, email: e.target.value }))}
                        onKeyDown={(e) => { if (e.key === "Enter") onLogin(); }}
                        placeholder="team@company.com"
                        className="input-field"
                      />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-xs font-medium text-slate-400">Password</label>
                      <input
                        value={auth.password}
                        type="password"
                        onChange={(e) => setAuth((s) => ({ ...s, password: e.target.value }))}
                        onKeyDown={(e) => { if (e.key === "Enter") onLogin(); }}
                        placeholder="••••••••"
                        className="input-field"
                      />
                    </div>
                    <button
                      onClick={onLogin}
                      disabled={isLoggingIn}
                      className="w-full rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:opacity-90 active:scale-[.98] disabled:opacity-60"
                    >
                      {isLoggingIn ? "Signing in…" : "Sign in →"}
                    </button>
                    {authError && (
                      <div className="flex items-center gap-2 rounded-xl border border-rose-500/25 bg-rose-500/10 px-3 py-2">
                        <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-rose-400" />
                        <p className="text-xs text-rose-300">{authError}</p>
                      </div>
                    )}
                    <div className="rounded-xl border border-slate-800 bg-slate-950/45 px-3 py-3 text-[11px] text-slate-400">
                      <p className="font-medium text-slate-200">Operator access</p>
                      <p className="mt-1">
                        {isFirstWorkspaceOwnerFlow
                          ? "Create the first workspace owner with your work email, then invite analysts and reviewers once you are inside."
                          : "Sign in with your workspace credentials or create a new analyst workspace with your work email to begin investigating wallets."}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div>
                    <h3 className="text-sm font-semibold text-white">Create your workspace</h3>
                    <p className="mt-1 text-xs text-slate-500">
                      {previewAuthEnabled
                        ? "Email signup is production-ready today. SSO and phone OTP remain available below as clearly marked preview flows."
                        : "Email signup is production-ready today and keeps onboarding simple for new analyst teams."}
                    </p>

                    <div className="mt-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/8 px-4 py-3 text-[11px] text-emerald-100">
                      {isFirstWorkspaceOwnerFlow
                        ? "Create the first workspace owner with work email + password. That account will land as admin and can invite the rest of the team after setup."
                        : "Create an analyst workspace with work email + password, then start reviewing live wallets, alerts, and investigations immediately."}
                    </div>

                    <div className="mt-4 space-y-2.5">
                      <label className="text-[11px] text-slate-400">Work email</label>
                      <input
                        value={signupForm.email}
                        onChange={(e) => setSignupForm((s) => ({ ...s, email: e.target.value }))}
                        placeholder="team@company.com"
                        className="input-field"
                      />
                      <label className="text-[11px] text-slate-400">Create password</label>
                      <input
                        value={signupForm.password}
                        type="password"
                        onChange={(e) => setSignupForm((s) => ({ ...s, password: e.target.value }))}
                        placeholder="At least 8 characters"
                        className="input-field"
                      />
                      <label className="text-[11px] text-slate-400">Confirm password</label>
                      <input
                        value={signupForm.confirmPassword}
                        type="password"
                        onChange={(e) => setSignupForm((s) => ({ ...s, confirmPassword: e.target.value }))}
                        placeholder="Re-enter password"
                        className="input-field"
                      />
                      <button
                        onClick={onSignupEmail}
                        disabled={signupBusy}
                        className="w-full rounded-xl bg-gradient-to-r from-violet-500 to-fuchsia-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-500/20 transition hover:opacity-90 active:scale-[.98] disabled:opacity-60"
                      >
                        {signupBusy ? "Creating workspace…" : "Create workspace"}
                      </button>
                    </div>

                    {previewAuthEnabled && <details className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/45 p-4">
                      <summary className="cursor-pointer list-none text-sm font-semibold text-white">
                        Preview auth options
                      </summary>
                      <p className="mt-2 text-xs leading-relaxed text-slate-400">
                        These flows are intentionally labeled as previews because they do not complete full provider redirects yet. Keep email auth as the primary shipping path until those integrations are finished.
                      </p>

                      <div className="mt-4 grid gap-2 sm:grid-cols-2">
                        <button onClick={() => onSocialSignup("Google")} disabled={signupBusy} className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-700 bg-slate-900/70 px-3 py-2 text-xs text-slate-300 transition hover:border-slate-500 hover:text-white disabled:opacity-60">
                          <Chrome className="h-3.5 w-3.5" />Google preview
                        </button>
                        <button onClick={() => onSocialSignup("Apple")} disabled={signupBusy} className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-700 bg-slate-900/70 px-3 py-2 text-xs text-slate-300 transition hover:border-slate-500 hover:text-white disabled:opacity-60">
                          <Apple className="h-3.5 w-3.5" />Apple preview
                        </button>
                      </div>

                      <div className="mt-4 grid gap-2.5">
                        <label className="text-[11px] text-slate-400">Preview phone number</label>
                        <input
                          value={signupForm.phone}
                          onChange={(e) => setSignupForm((s) => ({ ...s, phone: e.target.value }))}
                          placeholder="+1 234 567 8901"
                          className="input-field"
                        />
                        <label className="text-[11px] text-slate-400">Preview verification code</label>
                        <input
                          value={signupForm.code}
                          onChange={(e) => setSignupForm((s) => ({ ...s, code: e.target.value }))}
                          placeholder="Enter preview code"
                          className="input-field"
                        />
                      </div>

                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <button
                          onClick={onPhoneStart}
                          disabled={signupBusy}
                          className="rounded-xl border border-cyan-500/35 bg-cyan-500/10 px-3 py-2 text-xs font-semibold text-cyan-200 transition hover:bg-cyan-500/20 disabled:opacity-60"
                        >
                          Send preview code
                        </button>
                        <button
                          onClick={onPhoneVerify}
                          disabled={signupBusy}
                          className="rounded-xl border border-emerald-500/35 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-200 transition hover:bg-emerald-500/20 disabled:opacity-60"
                        >
                          Verify preview code
                        </button>
                      </div>

                      {demoCodeHint && (
                        <div className="mt-3 rounded-xl border border-cyan-500/20 bg-cyan-500/8 px-3 py-2 text-xs text-cyan-100">
                          Preview code hint: <span className="font-semibold text-cyan-50">{demoCodeHint}</span>
                        </div>
                      )}
                    </details>}

                    {signupMessage && (
                      <div className={cn(
                        "mt-3 rounded-xl border px-3 py-2 text-xs",
                        /failed|could not|required|invalid|match|least/i.test(signupMessage)
                          ? "border-rose-500/25 bg-rose-500/10 text-rose-200"
                          : "border-cyan-500/25 bg-cyan-500/10 text-cyan-100",
                      )}>
                        {signupMessage}
                      </div>
                    )}
                  </div>
                )}
              </article>
            </div>

              <div className="grid gap-6 xl:grid-cols-[1.15fr_.85fr]">
                <article className="glass rounded-3xl p-6">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Why this gets bought</p>
                      <h3 className="mt-2 text-xl font-semibold text-white">Built for decisions, not just dashboards.</h3>
                    </div>
                    <span className="rounded-full border border-violet-500/25 bg-violet-500/10 px-3 py-1 text-[10px] uppercase tracking-[0.2em] text-violet-200">Premium operations value</span>
                  </div>
                  <div className="mt-5 grid gap-3 md:grid-cols-3">
                    <div className="value-card">
                      <LockKeyhole className="h-4 w-4 text-emerald-300" />
                      <p className="mt-3 text-sm font-semibold text-white">Explainable decisions</p>
                      <p className="mt-1 text-xs leading-relaxed text-slate-400">Each score is paired with narrative, fingerprints, recommended action, and audit-ready workflow history.</p>
                    </div>
                    <div className="value-card">
                      <Globe className="h-4 w-4 text-cyan-300" />
                      <p className="mt-3 text-sm font-semibold text-white">Live evidence where it matters</p>
                      <p className="mt-1 text-xs leading-relaxed text-slate-400">Ethereum wallets can be enriched and clustered live, which makes the experience useful on day one instead of waiting for integrations.</p>
                    </div>
                    <div className="value-card">
                      <BookmarkPlus className="h-4 w-4 text-amber-300" />
                      <p className="mt-3 text-sm font-semibold text-white">Analyst workflow included</p>
                      <p className="mt-1 text-xs leading-relaxed text-slate-400">Watchlists, alerts, incidents, cases, exports, and admin controls sit beside the intelligence so teams do not stitch tools together.</p>
                    </div>
                  </div>
                </article>

                <article className="glass rounded-3xl p-6">
                  <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Coverage and try-now wallets</p>
                  <div className="mt-4 space-y-3">
                    {SAMPLE_WALLET_PRESETS.map((preset) => (
                      <button
                        key={preset.address}
                        type="button"
                        onClick={() => applyWalletPreset(preset)}
                        className="sample-wallet-card w-full text-left"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full border border-cyan-500/25 bg-cyan-500/10 px-2 py-0.5 text-[9px] uppercase text-cyan-200">{preset.sourceLabel}</span>
                          <span className="rounded-full border border-slate-700 px-2 py-0.5 text-[9px] uppercase text-slate-300">{preset.category}</span>
                        </div>
                        <p className="mt-2 text-sm font-semibold text-white">{preset.title}</p>
                        <p className="mt-1 font-mono text-[10px] text-slate-500">{preset.address}</p>
                        <p className="mt-2 text-xs leading-relaxed text-slate-400">{preset.description}</p>
                      </button>
                    ))}
                  </div>
                  <div className="mt-5 rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                    <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Chain coverage today</p>
                    <div className="mt-3 space-y-3">
                      {COVERAGE_NOTES.map((item) => (
                        <div key={item.chain} className="rounded-2xl border border-slate-800 bg-slate-950/40 px-3 py-3">
                          <p className="text-xs font-semibold text-white">{item.chain}</p>
                          <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{item.mode}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </article>
              </div>
            </div>
          )}

          {/* ── Page title & change-password — only when signed in ──────── */}
          {loggedIn && (
            <div className="space-y-5 animate-fade-in-up">
              <section className="terminal-panel overflow-hidden rounded-3xl p-6">
                <div className="grid gap-5 lg:grid-cols-[1.3fr_.9fr]">
                  <div className="space-y-4">
                    <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-emerald-300">
                      <span className="h-2 w-2 rounded-full bg-emerald-400 pulse-dot" />
                      Intelligence console online
                    </div>
                    <div>
                      <h1 className="max-w-3xl text-3xl font-bold tracking-tight text-white sm:text-4xl">The analyst cockpit for high-velocity crypto investigations.</h1>
                      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-300">
                        Surface the highest-signal wallets, trace suspicious relationships, and move from alert to case decision in under five seconds.
                      </p>
                    </div>
                    <div className="rounded-2xl border border-indigo-500/20 bg-indigo-500/8 p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-indigo-500/25 bg-indigo-500/15 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-indigo-200">Current desk focus</span>
                        <span className="rounded-full border border-slate-700 bg-slate-950/70 px-2.5 py-1 text-[10px] uppercase tracking-[0.2em] text-slate-300">{primaryInvestigation?.chain ?? topPriorityAlert?.chain ?? "ready"}</span>
                        <span className="rounded-full border border-slate-700 bg-slate-950/70 px-2.5 py-1 text-[10px] uppercase tracking-[0.2em] text-slate-300">{primaryInvestigation?.riskLevel ?? topPriorityAlert?.risk_level ?? "monitoring"}</span>
                      </div>
                      <h2 className="mt-3 text-xl font-semibold text-white">{deskHeadline}</h2>
                      <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-300">{deskNarrative}</p>
                      <p className="mt-3 text-xs leading-relaxed text-slate-400">Next best action: {deskNextAction}</p>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-3">
                      {missionHighlights.map((item) => (
                        <div key={item.label} className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-3">
                          <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">{item.label}</p>
                          <p className={cn("mt-2 text-2xl font-bold", item.tone)}>{item.value}</p>
                          <p className="mt-1 text-[11px] text-slate-500">{item.detail}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div className="rounded-2xl border border-slate-800/80 bg-slate-950/40 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Launch actions</p>
                          <h2 className="mt-2 text-lg font-semibold text-white">Move the desk forward in one click.</h2>
                        </div>
                        <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.2em] text-emerald-200">Operator shortcuts</span>
                      </div>
                      <div className="mt-4 grid gap-2 sm:grid-cols-2">
                        <button type="button" onClick={() => applyWalletPreset(SAMPLE_WALLET_PRESETS[1])} className="command-chip justify-center">Load Binance sample</button>
                        <button type="button" onClick={() => applyWalletPreset(SAMPLE_WALLET_PRESETS[0])} className="command-chip justify-center">Load Vitalik sample</button>
                        <button type="button" onClick={onAnalyze} disabled={loadingIntel || session?.role === "viewer"} className="command-chip justify-center disabled:opacity-60">Run intelligence</button>
                        <button type="button" onClick={onLoadCluster} disabled={loadingCluster || !canLoadCluster} className="command-chip justify-center disabled:opacity-60">{clusterActionLabel}</button>
                        <button type="button" onClick={seedCaseDraftFromActiveWallet} className="command-chip justify-center">Pre-fill case draft</button>
                        <button type="button" onClick={onQuickWatch} disabled={!intelligence || session?.role === "viewer"} className="command-chip justify-center disabled:opacity-60">Watch active wallet</button>
                      </div>
                    </div>

                    <div className="rounded-2xl border border-slate-800/80 bg-slate-950/40 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Priority signal</p>
                          <h2 className="mt-2 text-lg font-semibold text-white">{topPriorityAlert ? topPriorityAlert.title : "No urgent alerts"}</h2>
                        </div>
                        {topPriorityAlert && (
                          <span className={cn("rounded-full border px-2 py-1 text-[10px] font-semibold uppercase", riskTone(topPriorityAlert.risk_level))}>
                            {topPriorityAlert.risk_level}
                          </span>
                        )}
                      </div>
                      <p className="mt-3 text-xs leading-relaxed text-slate-400">
                        {topPriorityAlert ? topPriorityAlert.body : "System is clear. Run a wallet analysis or monitor the live stream for new events."}
                      </p>
                      <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
                        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
                          <p className="text-slate-500">Chain</p>
                          <p className="mt-1 font-medium text-white">{topPriorityAlert?.chain ?? "—"}</p>
                        </div>
                        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
                          <p className="text-slate-500">Response</p>
                          <p className="mt-1 font-medium text-white">{alertUnread > 0 ? `${alertUnread} pending` : "Cleared"}</p>
                        </div>
                      </div>
                    </div>

                    <details className="rounded-xl border border-slate-800/80 bg-slate-900/40 px-4 py-3">
                      <summary className="cursor-pointer select-none text-xs font-medium text-slate-500 hover:text-slate-300">Operator security</summary>
                      <div className="mt-3 space-y-2">
                        <input type="password" value={passwordForm.current_password} onChange={(e) => setPasswordForm((s) => ({ ...s, current_password: e.target.value }))} placeholder="Current password" className="input-field" />
                        <input type="password" value={passwordForm.new_password} onChange={(e) => setPasswordForm((s) => ({ ...s, new_password: e.target.value }))} placeholder="New password" className="input-field" />
                        <button onClick={onChangePassword} disabled={passwordBusy} className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-medium text-white transition hover:bg-slate-700 disabled:opacity-60">
                          {passwordBusy ? "Updating…" : "Update password"}
                        </button>
                        {passwordMessage && <p className="text-xs text-slate-400">{passwordMessage}</p>}
                      </div>
                    </details>
                  </div>
                </div>
              </section>
            </div>
          )}
        </header>

        {/* ── Dashboard tab content ────────────────────────────────────── */}
        {activeTab === "dashboard" && loggedIn && (<>

        {/* Stat cards */}
        <section className="space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Operations snapshot</p>
              <h2 className="text-xl font-semibold text-white">What needs attention right now.</h2>
              <p className="text-sm text-slate-400">Use this strip to judge queue pressure before diving into intelligence, alerts, or casework.</p>
            </div>
            <div className="rounded-full border border-slate-800 bg-slate-950/60 px-3 py-1.5 text-[11px] text-slate-300">
              {alertUnread > 0 ? `${alertUnread} unread signals waiting` : "Queue is currently under control"}
            </div>
          </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard accent="indigo" title="Wallets Monitored" value={`${dashboard?.total_wallets_monitored ?? 0}`} icon={<Activity className="h-5 w-5 text-indigo-300" />} />
          <StatCard accent="amber"  title="Alerts Today"      value={`${dashboard?.alerts_today ?? 0}`}            icon={<AlertTriangle className="h-5 w-5 text-amber-300" />} />
          <StatCard accent="rose"   title="Critical Alerts"   value={`${dashboard?.critical_alerts_today ?? 0}`}   icon={<BadgeDollarSign className="h-5 w-5 text-rose-300" />} />
          <StatCard accent="cyan"   title="Watched Wallets"   value={`${watchlist.length}`}                           icon={<Eye className="h-5 w-5 text-cyan-300" />} />
        </div>

        <div className="grid gap-3 xl:grid-cols-[1.05fr_1.05fr_1.2fr]">
          {operatorBriefItems.map((item) => (
            <article key={item.label} className={cn("rounded-2xl border p-4 backdrop-blur-md", item.tone)}>
              <p className="text-[10px] uppercase tracking-[0.22em] text-slate-400">{item.label}</p>
              <h3 className="mt-2 text-base font-semibold">{item.value}</h3>
              <p className="mt-2 text-xs leading-relaxed text-slate-300">{item.detail}</p>
            </article>
          ))}
        </div>
        </section>

        {loggedIn && !hasWorkspaceActivity && (
          <section className="mt-4 grid gap-4 xl:grid-cols-[1.15fr_.85fr]">
            <article className="terminal-panel rounded-3xl p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">First-run workspace</p>
                  <h2 className="mt-2 text-xl font-semibold text-white">This desk is clean and ready for its first investigation.</h2>
                  <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-400">Use a sample wallet to see the full analyst workflow, then convert the result into watchlist coverage, alerts, and a documented case.</p>
                </div>
                <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-[10px] uppercase tracking-[0.2em] text-emerald-200">Zero noise start</span>
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-3">
                <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Best first click</p>
                  <p className="mt-2 text-sm font-semibold text-white">Load a validated wallet</p>
                  <p className="mt-1 text-xs leading-relaxed text-slate-400">Start with Binance hot wallet if you want the richest live graph and operational context.</p>
                </div>
                <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Fastest value</p>
                  <p className="mt-2 text-sm font-semibold text-white">Run live fill + intelligence</p>
                  <p className="mt-1 text-xs leading-relaxed text-slate-400">That immediately produces score, explanation, fingerprints, and the action recommendation teams actually need.</p>
                </div>
                <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Next operational step</p>
                  <p className="mt-2 text-sm font-semibold text-white">Escalate only if warranted</p>
                  <p className="mt-1 text-xs leading-relaxed text-slate-400">Open a case, watch the wallet, or inspect the cluster without leaving this screen.</p>
                </div>
              </div>
            </article>

            <article className="glass rounded-3xl p-5">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/15">
                  <Sparkles className="h-4 w-4 text-indigo-300" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-white">Starter actions</h2>
                  <p className="text-[10px] text-slate-500">Use one click to get the desk moving.</p>
                </div>
              </div>
              <div className="mt-4 flex flex-col gap-2">
                <button onClick={() => applyWalletPreset(SAMPLE_WALLET_PRESETS[1])} className="command-chip justify-center">Load Binance hot wallet</button>
                <button onClick={() => applyWalletPreset(SAMPLE_WALLET_PRESETS[0])} className="command-chip justify-center">Load Vitalik wallet</button>
                <button onClick={seedCaseDraftFromActiveWallet} className="command-chip justify-center">Pre-fill case draft</button>
              </div>
              <div className="mt-4 rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4 text-xs text-slate-400">
                Tip: once intelligence is on screen, add the wallet to the watchlist to see the monitoring workflow end-to-end.
              </div>
            </article>
          </section>
        )}

        {loggedIn && (
          <section className="mt-4 grid gap-4 xl:grid-cols-[1.1fr_.9fr]">
            <article className="glass rounded-2xl p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">How to use this desk</p>
                  <h2 className="mt-2 text-lg font-semibold text-white">A first-time operator can get value in under a minute.</h2>
                </div>
                <span className="rounded-full border border-indigo-500/25 bg-indigo-500/10 px-3 py-1 text-[10px] uppercase tracking-[0.2em] text-indigo-200">Self-guided workflow</span>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {quickStartChecklist.map((item, index) => (
                  <div key={item.title} className="workflow-card">
                    <div className="flex items-start gap-3">
                      <span className={cn("workflow-card-index", item.done && "workflow-card-index-done")}>{index + 1}</span>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold text-white">{item.title}</p>
                          {item.done && <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 text-[9px] uppercase text-emerald-300">done</span>}
                        </div>
                        <p className="mt-1 text-xs leading-relaxed text-slate-400">{item.detail}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </article>

            <article className="glass rounded-2xl p-5">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/15">
                  <Globe className="h-4 w-4 text-cyan-300" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-white">Try a validated wallet</h2>
                  <p className="text-[10px] text-slate-500">These samples were already useful in real-wallet QA.</p>
                </div>
              </div>
              <div className="mt-4 space-y-3">
                {SAMPLE_WALLET_PRESETS.map((preset) => (
                  <button
                    key={`${preset.address}-dashboard`}
                    type="button"
                    onClick={() => applyWalletPreset(preset)}
                    className="sample-wallet-card w-full text-left"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full border border-cyan-500/25 bg-cyan-500/10 px-2 py-0.5 text-[9px] uppercase text-cyan-200">{preset.chain}</span>
                      <span className="rounded-full border border-slate-700 px-2 py-0.5 text-[9px] uppercase text-slate-300">{preset.category}</span>
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-white">{preset.title}</p>
                      <span className="text-[10px] text-slate-500">Load sample</span>
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-slate-400">{preset.description}</p>
                  </button>
                ))}
              </div>
            </article>
          </section>
        )}

        {loggedIn && (
          <section className="mt-4 terminal-strip rounded-2xl px-3 py-2.5">
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
              <SignalPill label="Priority wallet" value={topPriorityAlert?.address ?? primaryInvestigation?.address ?? "Awaiting signal"} tone="rose" mono />
              <SignalPill label="Latest chain" value={topPriorityAlert?.chain ?? primaryInvestigation?.chain ?? "ethereum"} tone="cyan" />
              <SignalPill label="Case score" value={primaryInvestigation ? `${primaryInvestigation.score}/100` : "—"} tone="indigo" />
              <SignalPill label="Ops state" value={alertUnread > 0 ? `${alertUnread} alerts pending` : "Desk clear"} tone="amber" />
            </div>
          </section>
        )}

        {/* Charts row */}
        <section className="mt-6 grid gap-6 lg:grid-cols-[1.3fr_1fr]">
          <article className="glass rounded-2xl p-5">
            <h2 className="mb-3 text-base font-medium text-slate-100">7-Day Alert Trend</h2>
            <div className="h-52 w-full">
              {isMounted && trendData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trendData}>
                    <defs>
                      <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#7c8cff" stopOpacity={0.8} />
                        <stop offset="95%" stopColor="#7c8cff" stopOpacity={0.05} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
                    <XAxis dataKey="day" stroke="#94a3b8" />
                    <Tooltip contentStyle={{ background: "rgba(9,12,21,0.95)", border: "1px solid rgba(122,136,255,0.3)", borderRadius: 10 }} />
                    <Area type="monotone" dataKey="alerts" stroke="#8ea0ff" strokeWidth={2.5} fill="url(#trendFill)" />
                  </AreaChart>
                </ResponsiveContainer>
              ) : isMounted ? (
                <div className="flex h-full flex-col justify-between rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">No trend yet</p>
                    <p className="mt-2 text-sm font-semibold text-white">Your alert timeline will appear here after the desk sees activity.</p>
                    <p className="mt-2 max-w-md text-xs leading-relaxed text-slate-400">The fastest way to populate this is to run intelligence on a sample wallet, then add it to the watchlist so follow-on events can be tracked over time.</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={() => applyWalletPreset(SAMPLE_WALLET_PRESETS[1])} className="command-chip">Load Binance</button>
                    <button type="button" onClick={onAnalyze} disabled={loadingIntel || session?.role === "viewer"} className="command-chip disabled:opacity-60">Run intelligence</button>
                  </div>
                </div>
              ) : <div className="h-full w-full animate-pulse rounded-xl bg-slate-900/40" />}
            </div>
          </article>

          <article className="glass rounded-2xl p-5">
            <h2 className="mb-3 text-base font-medium text-slate-100">Alert Severity Breakdown</h2>
            <div className="flex h-48 items-center gap-4">
              {isMounted && severityData.length > 0 ? (
                <>
                  <ResponsiveContainer width="60%" height="100%">
                    <PieChart>
                      <Pie data={severityData} cx="50%" cy="50%" innerRadius={44} outerRadius={72} paddingAngle={3} dataKey="value" strokeWidth={0}>
                        {severityData.map((entry) => (
                          <Cell key={entry.name} fill={SEVERITY_COLORS[entry.name] ?? "#6366f1"} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ background: "rgba(9,12,21,0.95)", border: "1px solid rgba(122,136,255,0.3)", borderRadius: 10 }} />
                    </PieChart>
                  </ResponsiveContainer>
                  <ul className="flex flex-col gap-2 text-xs">
                    {severityData.map((entry) => (
                      <li key={entry.name} className="flex items-center gap-2">
                        <span className={cn("h-2.5 w-2.5 rounded-full", entry.name === "critical" && "bg-rose-500", entry.name === "high" && "bg-orange-500", entry.name === "medium" && "bg-yellow-500", entry.name === "low" && "bg-green-500")} />
                        <span className="capitalize text-slate-300">{entry.name}</span>
                        <span className="ml-auto pl-3 font-semibold text-white">{entry.value}</span>
                      </li>
                    ))}
                  </ul>
                </>
              ) : isMounted ? (
                <div className="grid h-full w-full place-items-center rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4 text-center">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Severity mix unavailable</p>
                    <p className="mt-2 text-sm font-semibold text-white">No alert severities to summarize yet.</p>
                    <p className="mt-2 max-w-xs text-xs leading-relaxed text-slate-400">Once watchlisted wallets or scored activity trigger events, this chart will show how much of your queue is low, medium, high, or critical.</p>
                    <div className="mt-4 flex flex-wrap justify-center gap-2">
                      <button type="button" onClick={() => applyWalletPreset(SAMPLE_WALLET_PRESETS[2])} className="command-chip">Load USDC</button>
                      <button type="button" onClick={() => applyWalletPreset(SAMPLE_WALLET_PRESETS[1])} className="command-chip">Load Binance</button>
                    </div>
                  </div>
                </div>
              ) : <div className="h-full w-full animate-pulse rounded-xl bg-slate-900/40" />}
            </div>
          </article>
        </section>

        {/* Investigation workspace */}
        <section className="mt-6 grid gap-6 lg:grid-cols-[1.35fr_.95fr]">
          <article className="terminal-panel rounded-3xl p-5">
            <div className="panel-header">
              <span className="panel-header-icon bg-indigo-500/15">
                <Activity className="h-4 w-4 text-indigo-300" />
              </span>
              <div>
                <h2 className="text-sm font-semibold text-white">Investigation Workspace</h2>
                <p className="text-[10px] text-slate-500">Persistent case timeline, evidence, notes, and linked entities</p>
              </div>
              <div className="ml-auto flex items-center gap-2">
                <select
                  value={caseFilter}
                  onChange={(event) => setCaseFilter(event.target.value as "all" | CaseStatus)}
                  aria-label="Filter cases by status"
                  className="rounded-full border border-slate-800 bg-slate-950/70 px-3 py-1.5 text-[10px] uppercase tracking-[0.2em] text-slate-300 outline-none"
                >
                  <option value="all">All cases</option>
                  <option value="open">Open</option>
                  <option value="in_review">In review</option>
                  <option value="escalated">Escalated</option>
                  <option value="closed">Closed</option>
                </select>
                <span className="rounded-full border border-slate-800 bg-slate-950/60 px-3 py-1 text-[10px] uppercase tracking-[0.2em] text-slate-400">{cases.length} tracked</span>
              </div>
            </div>

            {caseError && <div className="mb-4 rounded-2xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-xs text-rose-200">{caseError}</div>}
            {caseMessage && <div className="mb-4 rounded-2xl border border-emerald-500/25 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-200">{caseMessage}</div>}

            {activeCase ? (
              <div className="grid gap-4 xl:grid-cols-[1.1fr_.9fr]">
                <div className="space-y-4">
                  <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={cn("rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase", riskTone(activeCase.risk_level))}>{activeCase.risk_level}</span>
                      <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-1 text-[10px] uppercase text-violet-200">{activeCase.priority}</span>
                      <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-[10px] uppercase text-cyan-300">{activeCase.status.replace("_", " ")}</span>
                      {activeCase.primary_chain && <span className="rounded-full border border-slate-700 bg-slate-900/70 px-2.5 py-1 text-[10px] uppercase text-slate-300">{activeCase.primary_chain}</span>}
                      <span className="ml-auto text-[10px] text-slate-500">Updated {formatDistanceToNow(new Date(activeCase.updated_at), { addSuffix: true })}</span>
                    </div>
                    <div className="mt-4 grid gap-4 md:grid-cols-[auto_1fr] md:items-start">
                      <div className="risk-ring">
                        <div className="risk-ring-inner">
                          <span className="text-3xl font-bold text-white">{activeCase.risk_score}</span>
                          <span className="text-[10px] uppercase tracking-[0.2em] text-slate-500">score</span>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-lg font-semibold text-white">{activeCase.title}</h3>
                          <span className="rounded-full border border-slate-800 bg-slate-900/70 px-2 py-1 text-[10px] uppercase text-slate-400">Owner {activeCase.owner_email || "unassigned"}</span>
                        </div>
                        {activeCase.primary_address && <p className="font-mono text-xs text-slate-300 break-all">{activeCase.primary_address}</p>}
                        <p className="text-sm leading-relaxed text-slate-300">{activeCase.summary}</p>
                        {activeCase.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            {activeCase.tags.map((tag) => (
                              <span key={tag} className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-1 text-[10px] text-violet-200">{tag}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {(["open", "in_review", "escalated", "closed"] as CaseStatus[]).map((status) => (
                        <button
                          key={status}
                          type="button"
                          onClick={() => void onCaseStatusChange(status)}
                          disabled={caseBusy || activeCase.status === status}
                          className={cn(
                            "rounded-full border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] transition",
                            activeCase.status === status
                              ? "border-cyan-400/40 bg-cyan-500/15 text-cyan-200"
                              : "border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                          )}
                        >
                          {status.replace("_", " ")}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="grid gap-4 lg:grid-cols-2">
                    <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                      <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Timeline</p>
                      <div className="mt-4 space-y-3">
                        {activeCase.timeline.length > 0 ? activeCase.timeline.slice(0, 6).map((entry) => (
                          <TimelineRow
                            key={entry.id}
                            title={entry.title}
                            body={`${entry.body} · ${entry.actor_email}`}
                            tone={activeCase.risk_level}
                          />
                        )) : <p className="text-xs text-slate-500">No timeline events yet.</p>}
                      </div>
                    </div>

                    <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                      <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Linked entities</p>
                      <div className="mt-4 space-y-2">
                        {activeCase.linked_entities.length > 0 ? activeCase.linked_entities.slice(0, 6).map((entity) => (
                          <div key={entity.id} className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
                            <div className="flex items-center gap-2 text-xs">
                              <span className="rounded-full border border-slate-700 bg-slate-950/70 px-2 py-0.5 uppercase text-slate-300">{entity.entity_type}</span>
                              {entity.risk_level && <span className={cn("rounded-full border px-2 py-0.5 uppercase", riskTone(entity.risk_level))}>{entity.risk_level}</span>}
                            </div>
                            <p className="mt-2 text-sm font-medium text-white">{entity.label}</p>
                            <p className="font-mono text-[11px] text-slate-400 break-all">{entity.reference}</p>
                          </div>
                        )) : <p className="text-xs text-slate-500">No wallets, alerts, or clusters linked yet.</p>}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                    <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Analyst notes</p>
                    <div className="mt-4 space-y-2">
                      {activeCase.notes.length > 0 ? activeCase.notes.slice(0, 5).map((note) => (
                        <div key={note.id} className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
                          <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-slate-500">
                            <span>{note.note_type}</span>
                            <span>•</span>
                            <span>{note.author_email}</span>
                          </div>
                          <p className="mt-2 text-sm text-slate-300">{note.body}</p>
                        </div>
                      )) : <p className="text-xs text-slate-500">Capture your first observation or decision.</p>}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                    <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Evidence & activity</p>
                    <div className="mt-4 space-y-2">
                      {activeCase.attachments.slice(0, 3).map((attachment) => (
                        <a key={attachment.id} href={attachment.file_url} target="_blank" rel="noreferrer" className="block rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2 hover:border-slate-700">
                          <p className="text-sm font-medium text-white">{attachment.file_name}</p>
                          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{attachment.content_type}</p>
                        </a>
                      ))}
                      {activeCase.activity.slice(0, 4).map((entry) => (
                        <div key={entry.id} className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
                          <p className="text-xs font-medium text-white">{entry.action}</p>
                          <p className="text-[11px] text-slate-500">{entry.details}</p>
                        </div>
                      ))}
                      {activeCase.attachments.length === 0 && activeCase.activity.length === 0 && <p className="text-xs text-slate-500">No evidence or activity yet.</p>}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="grid gap-4 rounded-2xl border border-slate-800/80 bg-slate-950/40 p-5 xl:grid-cols-[1.15fr_.85fr]">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">No active case selected</p>
                  <h3 className="mt-2 text-lg font-semibold text-white">Open an investigation when a wallet needs a durable record.</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-400">Cases are where you preserve analyst reasoning, link alerts and wallets, attach evidence, and keep a defensible escalation trail.</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button type="button" onClick={seedCaseDraftFromActiveWallet} className="command-chip">Pre-fill case draft</button>
                    <button type="button" onClick={() => applyWalletPreset(SAMPLE_WALLET_PRESETS[1])} className="command-chip">Load Binance sample</button>
                  </div>
                </div>
                <div className="space-y-2 rounded-2xl border border-slate-800 bg-slate-950/45 p-4 text-xs text-slate-400">
                  <p className="font-medium uppercase tracking-[0.2em] text-slate-500">Good case triggers</p>
                  <p>• A wallet scores high and needs human escalation.</p>
                  <p>• A VIP or treasury flow needs documented approval.</p>
                  <p>• An alert or cluster relationship needs evidence attached.</p>
                </div>
              </div>
            )}
          </article>

          <article className="glass rounded-3xl p-5">
            <div className="panel-header">
              <span className="panel-header-icon bg-cyan-500/15">
                <ShieldCheck className="h-4 w-4 text-cyan-300" />
              </span>
              <div>
                <h2 className="text-sm font-semibold text-white">Case Command Center</h2>
                <p className="text-[10px] text-slate-500">Open new investigations and enrich active ones</p>
              </div>
            </div>
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <OpsMetric label="Open cases" value={`${cases.filter((item) => item.status !== "closed").length}`} tone="indigo" />
                <OpsMetric label="Escalated" value={`${cases.filter((item) => item.status === "escalated").length}`} tone="rose" />
                <OpsMetric label="Unread alerts" value={`${alertUnread}`} tone="rose" />
                <OpsMetric label="Tracked entities" value={`${watchlist.length}`} tone="cyan" />
              </div>

              <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Create case</p>
                  <span className="rounded-full border border-slate-700 bg-slate-950/70 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-slate-300">Use after scoring or alert triage</span>
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-3">
                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2 text-xs text-slate-400">
                    <p className="font-medium text-slate-200">Best trigger</p>
                    <p className="mt-1">High-risk intelligence, unresolved alert context, or a VIP flow that needs documented approval.</p>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2 text-xs text-slate-400">
                    <p className="font-medium text-slate-200">Fastest path</p>
                    <p className="mt-1">Use “Pre-fill case” from the active wallet result, then adjust summary and priority before opening.</p>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2 text-xs text-slate-400">
                    <p className="font-medium text-slate-200">What to preserve</p>
                    <p className="mt-1">Reason for review, linked wallet or cluster, supporting evidence, and the final operator decision.</p>
                  </div>
                </div>
                <div className="mt-3 space-y-3">
                  <input value={caseForm.title} onChange={(event) => setCaseForm((state) => ({ ...state, title: event.target.value }))} placeholder="Case title" className="input-field w-full" />
                  <textarea value={caseForm.summary} onChange={(event) => setCaseForm((state) => ({ ...state, summary: event.target.value }))} placeholder="Write the investigation hypothesis, trigger, or escalation rationale" className="input-field min-h-[92px] w-full resize-none" />
                  <div className="grid gap-3 sm:grid-cols-2">
                    <select aria-label="Select case priority" value={caseForm.priority} onChange={(event) => setCaseForm((state) => ({ ...state, priority: event.target.value as CasePriority }))} className="input-field w-full">
                      <option value="low">Low priority</option>
                      <option value="medium">Medium priority</option>
                      <option value="high">High priority</option>
                      <option value="critical">Critical priority</option>
                    </select>
                    <input value={caseForm.tags} onChange={(event) => setCaseForm((state) => ({ ...state, tags: event.target.value }))} placeholder="Tags comma-separated" className="input-field w-full" />
                  </div>
                  <button type="button" onClick={() => void onCreateCase()} disabled={caseBusy} className="inline-flex w-full items-center justify-center rounded-2xl border border-indigo-500/40 bg-indigo-500/15 px-4 py-2 text-sm font-semibold text-indigo-100 transition hover:bg-indigo-500/20 disabled:opacity-60">
                    {caseBusy ? "Opening case..." : "Open investigation"}
                  </button>
                </div>
              </div>

              {activeCase && (
                <>
                  <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                    <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Add note</p>
                    <div className="mt-3 space-y-3">
                      <select aria-label="Select note type" value={caseNoteForm.note_type} onChange={(event) => setCaseNoteForm((state) => ({ ...state, note_type: event.target.value as typeof state.note_type }))} className="input-field w-full">
                        <option value="observation">Observation</option>
                        <option value="hypothesis">Hypothesis</option>
                        <option value="evidence">Evidence</option>
                        <option value="decision">Decision</option>
                      </select>
                      <textarea value={caseNoteForm.body} onChange={(event) => setCaseNoteForm((state) => ({ ...state, body: event.target.value }))} placeholder="Capture analyst judgment, next step, or evidence note" className="input-field min-h-[88px] w-full resize-none" />
                      <input value={caseNoteForm.tags} onChange={(event) => setCaseNoteForm((state) => ({ ...state, tags: event.target.value }))} placeholder="Tags comma-separated" className="input-field w-full" />
                      <button type="button" onClick={() => void onAddCaseNote()} disabled={caseBusy} className="inline-flex w-full items-center justify-center rounded-2xl border border-cyan-500/40 bg-cyan-500/15 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-500/20 disabled:opacity-60">
                        Add note
                      </button>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                    <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Link entity</p>
                    <div className="mt-3 space-y-3">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <select aria-label="Select entity type" value={caseEntityForm.entity_type} onChange={(event) => setCaseEntityForm((state) => ({ ...state, entity_type: event.target.value as CaseEntityType }))} className="input-field w-full">
                          <option value="wallet">Wallet</option>
                          <option value="cluster">Cluster</option>
                          <option value="alert">Alert</option>
                          <option value="analysis">Analysis</option>
                          <option value="transaction">Transaction</option>
                        </select>
                        <input value={caseEntityForm.chain} onChange={(event) => setCaseEntityForm((state) => ({ ...state, chain: event.target.value }))} placeholder="Chain" className="input-field w-full" />
                      </div>
                      <input value={caseEntityForm.label} onChange={(event) => setCaseEntityForm((state) => ({ ...state, label: event.target.value }))} placeholder="Entity label" className="input-field w-full" />
                      <input value={caseEntityForm.reference} onChange={(event) => setCaseEntityForm((state) => ({ ...state, reference: event.target.value }))} placeholder="Address, alert id, analysis id, or tx hash" className="input-field w-full" />
                      <button type="button" onClick={() => void onAddCaseEntity()} disabled={caseBusy} className="inline-flex w-full items-center justify-center rounded-2xl border border-violet-500/40 bg-violet-500/15 px-4 py-2 text-sm font-semibold text-violet-100 transition hover:bg-violet-500/20 disabled:opacity-60">
                        Link entity
                      </button>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                    <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Attach evidence</p>
                    <div className="mt-3 space-y-3">
                      <input value={caseAttachmentForm.file_name} onChange={(event) => setCaseAttachmentForm((state) => ({ ...state, file_name: event.target.value }))} placeholder="Attachment label" className="input-field w-full" />
                      <input value={caseAttachmentForm.file_url} onChange={(event) => setCaseAttachmentForm((state) => ({ ...state, file_url: event.target.value }))} placeholder="URL or storage link" className="input-field w-full" />
                      <input value={caseAttachmentForm.content_type} onChange={(event) => setCaseAttachmentForm((state) => ({ ...state, content_type: event.target.value }))} placeholder="Type e.g. link, pdf, screenshot" className="input-field w-full" />
                      <button type="button" onClick={() => void onAddCaseAttachment()} disabled={caseBusy} className="inline-flex w-full items-center justify-center rounded-2xl border border-amber-500/40 bg-amber-500/15 px-4 py-2 text-sm font-semibold text-amber-100 transition hover:bg-amber-500/20 disabled:opacity-60">
                        Attach evidence
                      </button>
                    </div>
                  </div>
                </>
              )}

              <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Case queue</p>
                <div className="mt-3 space-y-2">
                  {cases.length > 0 ? cases.slice(0, 6).map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => void refreshCases(item.id)}
                      className={cn(
                        "w-full rounded-2xl border px-3 py-3 text-left transition",
                        selectedCaseId === item.id
                          ? "border-cyan-500/35 bg-cyan-500/10"
                          : "border-slate-800 bg-slate-900/60 hover:border-slate-700"
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <span className={cn("rounded-full border px-2 py-0.5 text-[9px] uppercase", riskTone(item.risk_level))}>{item.risk_level}</span>
                        <span className="rounded-full border border-slate-700 px-2 py-0.5 text-[9px] uppercase text-slate-300">{item.status.replace("_", " ")}</span>
                        <span className="ml-auto text-[10px] text-slate-500">#{item.id}</span>
                      </div>
                      <p className="mt-2 text-sm font-semibold text-white">{item.title}</p>
                      <p className="mt-1 line-clamp-2 text-xs text-slate-400">{item.summary}</p>
                    </button>
                  )) : <p className="text-xs text-slate-500">No cases yet. Use the form above to open the first investigation.</p>}
                </div>
              </div>
            </div>
          </article>
        </section>

        {/* Intelligence + Watchlist/Alerts row */}
        <section className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">

          {/* ── Intelligence panel ─────────────────────────────────────────── */}
          <article className="glass rounded-2xl p-5">
            <div className="mb-4 flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/15">
                <Zap className="h-4 w-4 text-amber-300" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">Wallet Intelligence</h2>
                <p className="text-[10px] text-slate-500">Fingerprint &amp; behavioral scoring</p>
              </div>
            </div>
            <div className="mb-4 rounded-2xl border border-indigo-500/20 bg-indigo-500/8 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-indigo-200">Current wallet</span>
                <span className="rounded-full border border-slate-700 bg-slate-950/70 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-slate-300">{walletBrief}</span>
                <span className={cn("rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.18em]", liveEnrichment ? "border-cyan-500/30 bg-cyan-500/10 text-cyan-200" : "border-slate-700 bg-slate-950/70 text-slate-400")}>{liveEnrichment ? "Live context loaded" : "Manual context"}</span>
                <span className={cn("rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.18em]", intelligence ? "border-violet-500/30 bg-violet-500/10 text-violet-200" : "border-slate-700 bg-slate-950/70 text-slate-400")}>{intelligence ? `Score ${intelligence.score}/100` : "Intelligence pending"}</span>
                <span className={cn("rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.18em]", currentWalletTracked ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200" : "border-slate-700 bg-slate-950/70 text-slate-400")}>{currentWalletTracked ? "Watchlisted" : "Not watchlisted"}</span>
              </div>
              <p className="mt-3 text-sm font-semibold text-white">Next best move</p>
              <p className="mt-1 text-sm leading-relaxed text-slate-300">{investigationNextMove}</p>
            </div>
            <div className="mb-4 rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Operator workflow</p>
                <span className="rounded-full border border-slate-700 bg-slate-950/70 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-slate-300">Guided analyst flow</span>
              </div>
              <div className="mt-3 grid gap-3 lg:grid-cols-[1.1fr_.9fr]">
                <div className="grid gap-2">
                  {quickStartChecklist.map((item, index) => (
                    <div key={item.title} className="workflow-card">
                      <div className="flex items-start gap-3">
                        <span className={cn("workflow-card-index", item.done && "workflow-card-index-done")}>{index + 1}</span>
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-semibold text-white">{item.title}</p>
                            {item.done && <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 text-[9px] uppercase text-emerald-300">done</span>}
                          </div>
                          <p className="mt-1 text-xs leading-relaxed text-slate-400">{item.detail}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-3 text-xs text-cyan-100">
                  <p className="font-semibold text-cyan-50">Why teams pay for this screen</p>
                  <p className="mt-2 leading-relaxed text-cyan-100/85">It compresses intake, chain context, explainable scoring, and escalation into one operator workflow. That reduces decision latency for high-value clients and risky inbound flows.</p>
                  <div className="mt-3 rounded-xl border border-cyan-500/20 bg-slate-950/30 px-3 py-2 text-[11px] leading-relaxed text-cyan-50/90">
                    Best path today: load an Ethereum wallet, use live fill, run intelligence, then open the relationship graph or pre-fill a case draft from the active result.
                  </div>
                </div>
              </div>
            </div>
            <div className="space-y-3 text-sm">
              <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">1. Intake wallet</p>
                <div className="mt-3 space-y-3">
                  <div>
                    <label className="mb-1 block text-xs text-slate-300">Chain</label>
                    <select value={walletInput.chain} onChange={(e) => setWalletInput((s) => ({ ...s, chain: e.target.value as Blockchain }))} aria-label="Select chain" className="w-full rounded-md border border-slate-700 bg-slate-900/80 px-2 py-1.5 text-xs uppercase outline-none focus:ring focus:ring-indigo-500">
                      {chainOptions.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <FormInput label="Wallet Address" value={walletInput.address} onChange={(v) => setWalletInput((s) => ({ ...s, address: v }))} />
                  <div>
                    <p className="mb-2 text-[10px] uppercase tracking-[0.2em] text-slate-500">Validated sample wallets</p>
                    <div className="grid gap-2 sm:grid-cols-3">
                      {SAMPLE_WALLET_PRESETS.map((preset) => (
                        <button
                          key={`${preset.address}-chip`}
                          type="button"
                          onClick={() => applyWalletPreset(preset)}
                          className="rounded-2xl border border-slate-800 bg-slate-950/45 px-3 py-2 text-left transition hover:border-cyan-500/35 hover:bg-slate-900/70"
                        >
                          <p className="text-[11px] font-semibold text-white">{preset.title}</p>
                          <p className="mt-1 text-[10px] text-slate-500">{preset.category}</p>
                        </button>
                      ))}
                    </div>
                  </div>
                  <button onClick={onEnrichWalletLive} disabled={loadingEnrich || !walletInput.address.trim()} className="w-full rounded-xl border border-cyan-500/40 bg-cyan-500/10 px-4 py-2.5 font-semibold text-cyan-100 transition hover:bg-cyan-500/15 active:scale-[.98] disabled:opacity-60">
                    {loadingEnrich ? "Fetching live wallet data…" : "🌐 Live Fill From Ethereum"}
                  </button>
                  <p className="text-[11px] leading-relaxed text-slate-500">
                    Live fill is strongest on Ethereum today. Other listed chains still benefit from manual scoring, watchlist coverage, incidents, and case workflows.
                  </p>
                  {liveEnrichment && (
                    <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 px-3 py-2 text-xs text-cyan-100">
                      <p>
                        Source: {liveEnrichment.source} · {liveEnrichment.recent_tx_scanned} tx scanned · ETH ${liveEnrichment.asset_price_usd.toLocaleString()} · Balance {liveEnrichment.balance_native.toLocaleString()} ETH
                      </p>
                    </div>
                  )}
                </div>
              </div>
              <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 p-4">
                <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">2. Analyst context</p>
                <div className="mt-3 space-y-3">
                  <FormInput label="Transactions (24h)" type="number" value={walletInput.txn_24h} onChange={(v) => setWalletInput((s) => ({ ...s, txn_24h: Number(v) || 0 }))} />
                  <FormInput label="Volume USD (24h)" type="number" value={walletInput.volume_24h_usd} onChange={(v) => setWalletInput((s) => ({ ...s, volume_24h_usd: Number(v) || 0 }))} />
                  <div className="grid grid-cols-3 gap-2">
                    <FormInput label="Sanctions %" type="number" value={walletInput.sanctions_exposure_pct} onChange={(v) => setWalletInput((s) => ({ ...s, sanctions_exposure_pct: Number(v) || 0 }))} />
                    <FormInput label="Mixer %" type="number" value={walletInput.mixer_exposure_pct} onChange={(v) => setWalletInput((s) => ({ ...s, mixer_exposure_pct: Number(v) || 0 }))} />
                    <FormInput label="Bridge hops" type="number" value={walletInput.bridge_hops} onChange={(v) => setWalletInput((s) => ({ ...s, bridge_hops: Number(v) || 0 }))} />
                  </div>
                </div>
              </div>

              <button onClick={onAnalyze} disabled={loadingIntel || session?.role === "viewer"} className="w-full rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 px-4 py-2.5 font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:opacity-90 active:scale-[.98] disabled:opacity-60">
                {session?.role === "viewer" ? "Read-only mode" : loadingIntel ? "Analyzing…" : "⚡ Run Intelligence"}
              </button>
              {intelError && <p className="text-xs text-rose-300">{intelError}</p>}

              {/* ── Result card ── */}
              {intelligence && (
                <div className="space-y-3 rounded-xl border border-slate-700/60 bg-slate-900/60 p-3">
                  {/* Header */}
                  {/* Header */}
                  <div className="flex flex-wrap items-center gap-2.5 border-b border-slate-700/40 pb-3">
                    <span className={cn("rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wider", riskTone(intelligence.risk_level))}>{intelligence.risk_level}</span>
                    <div className="flex items-baseline gap-1">
                      <span className="text-2xl font-bold text-white">{intelligence.score}</span>
                      <span className="text-xs text-slate-500">/100</span>
                    </div>
                    <span className="rounded-full border border-cyan-500/35 bg-cyan-500/10 px-2 py-0.5 text-[10px] uppercase text-cyan-200">{intelligence.chain}</span>
                    <span className="ml-auto text-[10px] text-slate-500">#{intelligence.analysis_id}</span>
                  </div>

                  {/* Recommended action */}
                  <div className={cn("flex items-center justify-between rounded-lg border px-3 py-2", ACTION_STYLES[intelligence.narrative.recommended_action])}>
                    <span className="text-sm font-semibold">{intelligence.narrative.recommended_action_label}</span>
                    <span className="text-xs opacity-75">Confidence: {Math.round(intelligence.narrative.confidence * 100)}%</span>
                  </div>

                  {/* Fingerprint badges */}
                  {intelligence.fingerprints.length > 0 && (
                    <div>
                      <p className="mb-1.5 text-[10px] uppercase tracking-wide text-slate-400">Behavior Fingerprints</p>
                      <div className="flex flex-wrap gap-1.5">
                        {intelligence.fingerprints.map((fp) => (
                          <span key={fp.label} title={fp.description} className="cursor-help rounded-full border border-violet-500/40 bg-violet-500/10 px-2.5 py-1 text-[11px] font-medium text-violet-200">
                            {fp.display} <span className="opacity-60">{fp.confidence}%</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Narrative */}
                  <div>
                    <p className="mb-1 text-[10px] uppercase tracking-wide text-slate-400">Narrative</p>
                    <p className="text-xs leading-relaxed text-slate-200">{intelligence.narrative.summary}</p>
                  </div>

                  {/* Business context */}
                  <div className="rounded-lg border border-slate-700/40 bg-slate-950/40 px-3 py-2">
                    <p className="text-[11px] leading-relaxed text-slate-400">{intelligence.narrative.business_context}</p>
                  </div>

                  {/* AI explanation */}
                  <div>
                    <p className="mb-1 text-[10px] uppercase tracking-wide text-slate-400">AI Explanation</p>
                    <p className="text-xs leading-relaxed text-slate-300">{intelligence.explanation}</p>
                  </div>

                  {/* Action buttons */}
                  {session?.role !== "viewer" && (
                    <div className="flex flex-wrap gap-2 border-t border-slate-700/40 pt-2">
                      <button onClick={onLoadCluster} disabled={loadingCluster} className="inline-flex items-center gap-1.5 rounded-md border border-indigo-500/40 bg-indigo-500/10 px-3 py-1.5 text-xs text-indigo-200 hover:bg-indigo-500/20 disabled:opacity-60">
                        <Globe className="h-3 w-3" />{walletInput.chain === "ethereum"
                          ? (loadingCluster ? "Loading…" : showCluster ? "Refresh Live Cluster" : "View Live Cluster")
                          : (loadingCluster ? "Loading…" : showCluster ? "Refresh Cluster" : "View Cluster")}
                      </button>
                      <button onClick={onQuickWatch} disabled={watchlistBusy} className="inline-flex items-center gap-1.5 rounded-md border border-cyan-500/40 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-200 hover:bg-cyan-500/20 disabled:opacity-60">
                        <BookmarkPlus className="h-3 w-3" />Watch
                      </button>
                      <button onClick={seedCaseDraftFromActiveWallet} className="inline-flex items-center gap-1.5 rounded-md border border-violet-500/40 bg-violet-500/10 px-3 py-1.5 text-xs text-violet-200 hover:bg-violet-500/20">
                        <LockKeyhole className="h-3 w-3" />Pre-fill case
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Cluster graph */}
              {showCluster && cluster && <ClusterGraph cluster={cluster} />}

              {/* Recent analyses */}
              <div className="rounded-xl border border-slate-700/60 bg-slate-950/50 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-xs uppercase tracking-wide text-slate-400">Recent Analyses</h3>
                  {session?.role !== "viewer" && (
                    <button onClick={onExportCSV} disabled={csvBusy} className="inline-flex items-center gap-1 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-2 py-1 text-[10px] text-emerald-300 hover:bg-emerald-500/20 disabled:opacity-60">
                      <Download className="h-3 w-3" />{csvBusy ? "Exporting…" : "CSV"}
                    </button>
                  )}
                </div>
                {csvMessage && <p className="mb-1 text-[10px] text-slate-400">{csvMessage}</p>}
                <div className="max-h-64 space-y-2 overflow-auto pr-1">
                  {analyses.length === 0 ? (
                    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-400">
                      <p className="font-medium text-slate-200">No analyses yet.</p>
                      <p className="mt-1 leading-relaxed">Run intelligence on a wallet to start building an analyst history you can export, tag, and revisit.</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button type="button" onClick={() => applyWalletPreset(SAMPLE_WALLET_PRESETS[0])} className="command-chip">Load Vitalik</button>
                        <button type="button" onClick={() => applyWalletPreset(SAMPLE_WALLET_PRESETS[1])} className="command-chip">Load Binance</button>
                      </div>
                    </div>
                  ) : analyses.map((item) => (
                    <div key={item.id} className="rounded-lg border border-slate-800 bg-slate-900/50 p-2">
                      <div className="mb-1 flex items-center justify-between">
                        <span className={cn("rounded-full border px-2 py-0.5 text-[10px] uppercase", riskTone(item.risk_level))}>{item.risk_level}</span>
                        <span className="text-[10px] text-slate-500">{formatDistanceToNow(new Date(item.created_at), { addSuffix: true })}</span>
                      </div>
                      <p className="truncate font-mono text-[11px] text-slate-300">{item.address}</p>
                      <div className="mt-1 flex items-center justify-between gap-2">
                        <p className="text-xs text-slate-400">Score {item.score}/100</p>
                        <span className="rounded-full border border-cyan-500/35 bg-cyan-500/10 px-2 py-0.5 text-[10px] uppercase text-cyan-200">{item.chain}</span>
                      </div>
                      {item.tags.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {item.tags.map((tag) => (
                            <span key={tag} className="inline-flex items-center gap-1 rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[10px] text-violet-300">
                              {tag}
                              {session?.role !== "viewer" && (
                                <button onClick={() => onRemoveTag(item.id, tag)} disabled={tagBusy} aria-label={`Remove ${tag}`} className="hover:text-rose-300 disabled:opacity-60"><X className="h-2.5 w-2.5" /></button>
                              )}
                            </span>
                          ))}
                        </div>
                      )}
                      {session?.role !== "viewer" && (
                        <div className="mt-1.5">
                          {taggingId === item.id ? (
                            <div className="flex flex-col gap-1">
                              <div className="flex flex-wrap gap-1">
                                {PRESET_TAGS.filter((pt) => !item.tags.includes(pt)).map((pt) => (
                                  <button key={pt} onClick={() => onAddTag(item.id, pt)} disabled={tagBusy} className="rounded-full border border-slate-600 bg-slate-800/60 px-2 py-0.5 text-[10px] text-slate-300 hover:border-violet-400/50 hover:text-violet-300 disabled:opacity-60">+ {pt}</button>
                                ))}
                              </div>
                              <div className="flex gap-1">
                                <input value={tagInput} onChange={(e) => setTagInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") onAddTag(item.id, tagInput); }} placeholder="Custom tag…" maxLength={32} className="flex-1 rounded-md border border-slate-700 bg-slate-900/80 px-2 py-1 text-[10px] text-slate-100 outline-none focus:ring focus:ring-violet-500" />
                                <button onClick={() => onAddTag(item.id, tagInput)} disabled={tagBusy || !tagInput.trim()} className="rounded-md bg-violet-600 px-2 py-1 text-[10px] text-white hover:bg-violet-500 disabled:opacity-60">Add</button>
                                <button onClick={() => { setTaggingId(null); setTagInput(""); setTagMessage(""); }} className="rounded-md border border-slate-700 px-2 py-1 text-[10px] text-slate-400 hover:bg-slate-800">Done</button>
                              </div>
                              {tagMessage && <p className="text-[10px] text-slate-400">{tagMessage}</p>}
                            </div>
                          ) : (
                            <button onClick={() => { setTaggingId(item.id); setTagInput(""); setTagMessage(""); }} className="inline-flex items-center gap-1 text-[10px] text-slate-500 hover:text-violet-300">
                              <Tag className="h-3 w-3" /> Tag
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </article>

          {/* ── Right column ─────────────────────────────────────────────────── */}
          <div className="flex flex-col gap-6">

            {/* Watchlist */}
            <article className="glass rounded-2xl p-5">
              <div className="panel-header">
                <span className="panel-header-icon bg-cyan-500/15">
                  <Eye className="h-4 w-4 text-cyan-300" />
                </span>
                <div>
                  <h2 className="text-sm font-semibold text-white">Watchlist</h2>
                  <p className="text-[10px] text-slate-500">Monitored addresses</p>
                </div>
                <span className="ml-auto rounded-full border border-slate-700 bg-slate-900/70 px-2.5 py-1 text-[10px] text-slate-400">{watchlist.length}</span>
              </div>
              <div className="mb-3 rounded-2xl border border-cyan-500/20 bg-cyan-500/6 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-cyan-200">Coverage queue</span>
                  <span className="rounded-full border border-slate-700 bg-slate-950/70 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-slate-300">{watchlist.length} tracked</span>
                  <span className="rounded-full border border-slate-700 bg-slate-950/70 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-slate-300">{currentWalletTracked ? "Current wallet monitored" : "Current wallet not tracked"}</span>
                </div>
                <p className="mt-3 text-xs leading-relaxed text-cyan-100/90">Use this list for wallets that should create future signal, not just one-time analysis. Good candidates include treasury destinations, VIP counterparties, recurring cash-out wallets, and any address linked to an escalated case.</p>
              </div>
              {session?.role !== "viewer" && (
                <div className="mb-3 space-y-2">
                  <div className="rounded-xl border border-slate-800 bg-slate-950/45 px-3 py-2 text-[11px] leading-relaxed text-slate-400">
                    Fastest add: prefill the active wallet if today’s analysis should keep generating alerts.
                  </div>
                  <select value={watchForm.chain} onChange={(e) => setWatchForm((s) => ({ ...s, chain: e.target.value as Blockchain }))} aria-label="Watchlist chain" className="w-full rounded-md border border-slate-700 bg-slate-900/80 px-2 py-1.5 text-xs outline-none focus:ring focus:ring-cyan-500">
                    {chainOptions.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                  <input value={watchForm.address} onChange={(e) => setWatchForm((s) => ({ ...s, address: e.target.value }))} placeholder="0x… wallet address" className="w-full rounded-md border border-slate-700 bg-slate-900/80 px-2 py-1.5 text-xs outline-none focus:ring focus:ring-cyan-500" />
                  <input value={watchForm.label} onChange={(e) => setWatchForm((s) => ({ ...s, label: e.target.value }))} placeholder="Label (e.g. Suspect entity)" className="w-full rounded-md border border-slate-700 bg-slate-900/80 px-2 py-1.5 text-xs outline-none focus:ring focus:ring-cyan-500" />
                  <button onClick={onAddWatchlist} disabled={watchlistBusy} className="w-full rounded-md bg-cyan-600 py-1.5 text-xs font-medium text-white hover:bg-cyan-500 disabled:opacity-60">
                    {watchlistBusy ? "Adding…" : "+ Add to Watchlist"}
                  </button>
                  {watchlistError && <p className="text-[10px] text-rose-300">{watchlistError}</p>}
                </div>
              )}
              <div className="max-h-52 space-y-2 overflow-auto pr-1">
                {watchlist.length === 0 ? (
                  <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-400">
                    <p className="font-medium text-slate-200">No watched wallets.</p>
                    <p className="mt-1 leading-relaxed">Use the watchlist for counterparties, treasury destinations, VIP senders, or any wallet that should trigger future attention.</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button type="button" onClick={() => setWatchForm((state) => ({ ...state, chain: "ethereum", address: SAMPLE_WALLET_PRESETS[1].address, label: "Binance hot wallet" }))} className="command-chip">Prefill Binance</button>
                      <button type="button" onClick={() => setWatchForm((state) => ({ ...state, chain: walletInput.chain, address: walletInput.address, label: intelligence ? `Monitor ${walletInput.address.slice(0, 8)}…` : "" }))} className="command-chip">Use current wallet</button>
                    </div>
                  </div>
                ) : watchlist.map((w) => (
                  <div key={w.id} className="flex items-start justify-between rounded-lg border border-slate-800 bg-slate-900/50 p-2">
                    <div className="min-w-0">
                      <p className="truncate text-[11px] font-medium text-slate-200">{w.label}</p>
                      <p className="truncate font-mono text-[10px] text-slate-500">{w.address}</p>
                      <div className="mt-0.5 flex items-center gap-1.5">
                        <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-1.5 py-0.5 text-[9px] uppercase text-cyan-300">{w.chain}</span>
                        {w.last_score !== null && <span className="text-[9px] text-slate-500">Score: {w.last_score}</span>}
                      </div>
                    </div>
                    {session?.role !== "viewer" && (
                      <button title="Remove from watchlist" onClick={() => onRemoveWatchlist(w.id)} disabled={watchlistBusy} className="ml-2 mt-0.5 shrink-0 text-slate-600 hover:text-rose-400 disabled:opacity-40">
                        <X className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </article>

            {/* Alert Events */}
            <article className="glass rounded-2xl p-5">
              <div className="panel-header">
                <span className="panel-header-icon bg-amber-500/15">
                  <Bell className="h-4 w-4 text-amber-300" />
                </span>
                <div>
                  <h2 className="text-sm font-semibold text-white">Alert Events</h2>
                  <p className="text-[10px] text-slate-500">Real-time risk signals</p>
                </div>
                {alertUnread > 0 && <span className="rounded-full bg-rose-500 px-2 py-0.5 text-[10px] font-bold text-white">{alertUnread}</span>}
                <div className="ml-auto flex items-center gap-2">
                  <button onClick={() => setShowUnackedOnly((v) => !v)} title="Toggle unread" className={cn("rounded-md border px-2 py-1 text-[10px]", showUnackedOnly ? "border-amber-500/50 bg-amber-500/10 text-amber-200" : "border-slate-700 text-slate-400 hover:bg-slate-800")}>
                    {showUnackedOnly ? <Bell className="h-3 w-3" /> : <BellOff className="h-3 w-3" />}
                  </button>
                  {alertUnread > 0 && session?.role !== "viewer" && (
                    <button onClick={onAckAll} disabled={alertBusy} className="rounded-md border border-slate-700 px-2 py-1 text-[10px] text-slate-400 hover:bg-slate-800 disabled:opacity-60">Ack all</button>
                  )}
                </div>
              </div>
              <div className="mb-3 rounded-2xl border border-amber-500/20 bg-amber-500/6 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-amber-200">Live alert queue</span>
                  <span className="rounded-full border border-slate-700 bg-slate-950/70 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-slate-300">{alertUnread} unread</span>
                  <span className="rounded-full border border-slate-700 bg-slate-950/70 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-slate-300">{showUnackedOnly ? "Unread filter on" : "All visible"}</span>
                </div>
                <p className="mt-3 text-xs leading-relaxed text-amber-100/90">This panel is for rapid queue clearing. Investigate here when you need immediate triage, then move durable work into incidents or cases once the signal is confirmed.</p>
              </div>
              <div className="max-h-64 space-y-2 overflow-auto pr-1">
                {visibleAlerts.length === 0 ? (
                  <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-400">
                    <p className="font-medium text-slate-200">{showUnackedOnly ? "No unread alerts." : "No alerts yet."}</p>
                    <p className="mt-1 leading-relaxed">Alerts appear when monitored wallets or scored activity cross meaningful thresholds. Acknowledge and resolve them from here once the desk is active.</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button type="button" onClick={() => applyWalletPreset(SAMPLE_WALLET_PRESETS[1])} className="command-chip">Load alert-rich sample</button>
                      <button type="button" onClick={onAnalyze} disabled={loadingIntel || session?.role === "viewer"} className="command-chip disabled:opacity-60">Run intelligence now</button>
                    </div>
                  </div>
                ) : visibleAlerts.map((alert) => (
                  <div key={alert.id} className={cn("rounded-lg border p-2.5 pl-3.5", alert.acknowledged ? "border-slate-800 bg-slate-900/40 opacity-60" : cn("border-slate-700/50 bg-slate-900/50", "alert-" + alert.risk_level))}>
                    <div className="mb-1 flex items-start justify-between gap-2">
                      <p className="text-[11px] font-medium leading-snug text-slate-100">{alert.title}</p>
                      {!alert.acknowledged && session?.role !== "viewer" && (
                        <button onClick={() => onAckAlert(alert.id)} disabled={alertBusy} className="shrink-0 rounded border border-slate-700 px-1.5 py-0.5 text-[9px] text-slate-400 hover:bg-slate-800 disabled:opacity-60">✓</button>
                      )}
                    </div>
                    <p className="text-[10px] leading-relaxed text-slate-400">{alert.body}</p>
                    <div className="mt-1.5 flex items-center gap-2">
                      <span className={cn("rounded-full border px-1.5 py-0.5 text-[9px] uppercase", riskTone(alert.risk_level))}>{alert.risk_level}</span>
                      <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-1.5 py-0.5 text-[9px] uppercase text-cyan-300">{alert.chain}</span>
                      <span className="ml-auto text-[9px] text-slate-600">{formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}</span>
                    </div>
                  </div>
                ))}
              </div>
            </article>

            {/* Admin-only panels */}
            {session?.role === "admin" && (
              <>
                {/* Audit Logs */}
                <article className="terminal-panel rounded-2xl p-5">
                  <div className="panel-header">
                    <span className="panel-header-icon bg-emerald-500/15">
                      <ShieldCheck className="h-4 w-4 text-emerald-300" />
                    </span>
                    <div>
                      <h2 className="text-sm font-semibold text-white">Audit Logs</h2>
                      <p className="text-[10px] text-slate-500">Immutable operator activity stream</p>
                    </div>
                  </div>
                  <div className="mb-3 rounded-2xl border border-emerald-500/18 bg-emerald-500/6 p-4 text-xs leading-relaxed text-emerald-100/90">
                    Use audit logs to prove who made a decision, when it happened, and which object changed. This is the first place a compliance lead should look when reviewing operator behavior.
                  </div>
                  <div className="max-h-40 space-y-2 overflow-auto pr-1">
                    {auditLogs.length === 0 ? <p className="text-xs text-slate-500">No logs yet.</p> : auditLogs.map((log) => (
                      <div key={log.id} className="rounded-lg border border-slate-800 bg-slate-900/50 p-2">
                        <p className="text-[11px] text-slate-300"><span className="font-medium text-slate-100">{log.action}</span> → {log.target}</p>
                        <p className="text-[10px] text-slate-500">{log.actor_email}</p>
                      </div>
                    ))}
                  </div>
                </article>

                {/* Webhooks */}
                <article className="terminal-panel rounded-2xl p-5">
                  <div className="panel-header">
                    <span className="panel-header-icon bg-violet-500/15">
                      <Webhook className="h-4 w-4 text-violet-300" />
                    </span>
                    <div>
                      <h2 className="text-sm font-semibold text-white">Webhooks</h2>
                      <p className="text-[10px] text-slate-500">Outbound automation and alert delivery</p>
                    </div>
                  </div>
                  <div className="mb-3 rounded-2xl border border-violet-500/18 bg-violet-500/6 p-4 text-xs leading-relaxed text-violet-100/90">
                    Send alert events into Slack, case management, or internal orchestration once the desk logic is trusted. Keep this lightweight until your alert thresholds are stable.
                  </div>
                  <div className="mb-3 space-y-2">
                    <input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://your-server.com/webhook" className="w-full rounded-md border border-slate-700 bg-slate-900/80 px-2 py-1.5 text-xs outline-none focus:ring focus:ring-violet-500" />
                    <div className="flex flex-wrap gap-2">
                      {WEBHOOK_EVENTS.map((ev) => (
                        <label key={ev} className="flex cursor-pointer items-center gap-1.5 text-[10px] text-slate-300">
                          <input type="checkbox" checked={webhookEvents.includes(ev)} onChange={(e) => setWebhookEvents((prev) => e.target.checked ? [...prev, ev] : prev.filter((x) => x !== ev))} className="accent-violet-500" />
                          {ev}
                        </label>
                      ))}
                    </div>
                    <button onClick={onCreateWebhook} disabled={webhookBusy} className="w-full rounded-md bg-violet-700 py-1.5 text-xs font-medium text-white hover:bg-violet-600 disabled:opacity-60">
                      {webhookBusy ? "Adding…" : "+ Add Webhook"}
                    </button>
                    {webhookError && <p className="text-[10px] text-rose-300">{webhookError}</p>}
                  </div>
                  <div className="max-h-40 space-y-2 overflow-auto pr-1">
                    {webhooks.length === 0 ? <p className="text-xs text-slate-500">No webhooks configured.</p> : webhooks.map((wh) => (
                      <div key={wh.id} className="flex items-start justify-between rounded-lg border border-slate-800 bg-slate-900/50 p-2">
                        <div className="min-w-0">
                          <p className="truncate text-[10px] text-slate-300">{wh.url}</p>
                          <p className="text-[9px] text-slate-500">{wh.events.join(", ")}</p>
                        </div>
                        <button title="Delete webhook" onClick={() => onDeleteWebhook(wh.id)} disabled={webhookBusy} className="ml-2 shrink-0 text-slate-600 hover:text-rose-400 disabled:opacity-40">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                </article>

                {/* Team management */}
                <article className="terminal-panel rounded-2xl p-5">
                  <div className="panel-header">
                    <span className="panel-header-icon bg-indigo-500/15">
                      <ShieldCheck className="h-4 w-4 text-indigo-300" />
                    </span>
                    <div>
                      <h2 className="text-sm font-semibold text-white">Team Management</h2>
                      <p className="text-[10px] text-slate-500">Workspace access, invites, and operator roles</p>
                    </div>
                  </div>
                  <div className="mb-3 rounded-2xl border border-indigo-500/18 bg-indigo-500/6 p-4 text-xs leading-relaxed text-indigo-100/90">
                    Keep admins limited, analysts operational, and viewers read-only. This area is where you stage temporary credentials, invite links, and role hygiene before going fully production SSO.
                  </div>
                  <div className="mb-3 grid grid-cols-1 gap-2">
                    <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Create direct user</p>
                    <input value={teamForm.email} onChange={(e) => setTeamForm((s) => ({ ...s, email: e.target.value }))} placeholder="new-user@company.com" className="w-full rounded-md border border-slate-700 bg-slate-900/80 px-2 py-1.5 text-xs outline-none focus:ring focus:ring-indigo-500" />
                    <input type="password" value={teamForm.password} onChange={(e) => setTeamForm((s) => ({ ...s, password: e.target.value }))} placeholder="Temporary password" className="w-full rounded-md border border-slate-700 bg-slate-900/80 px-2 py-1.5 text-xs outline-none focus:ring focus:ring-indigo-500" />
                    <select aria-label="Select user role" value={teamForm.role} onChange={(e) => setTeamForm((s) => ({ ...s, role: e.target.value as TeamUserCreateRequest["role"] }))} className="w-full rounded-md border border-slate-700 bg-slate-900/80 px-2 py-1.5 text-xs outline-none focus:ring focus:ring-indigo-500">
                      <option value="admin">admin</option>
                      <option value="analyst">analyst</option>
                      <option value="viewer">viewer</option>
                    </select>
                    <button onClick={onCreateTeamUser} disabled={teamBusy} className="rounded-md bg-indigo-500 px-2 py-1.5 text-xs font-medium text-white hover:bg-indigo-400 disabled:opacity-60">
                      {teamBusy ? "Creating…" : "Create user"}
                    </button>
                    {teamError && <p className="text-xs text-rose-300">{teamError}</p>}
                  </div>
                  <div className="mb-3 grid grid-cols-1 gap-2 border-t border-slate-800 pt-3">
                    <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Create invite</p>
                    <input value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="invite-user@company.com" className="w-full rounded-md border border-slate-700 bg-slate-900/80 px-2 py-1.5 text-xs outline-none focus:ring focus:ring-indigo-500" />
                    <select aria-label="Select invite role" value={inviteRole} onChange={(e) => setInviteRole(e.target.value as TeamUserCreateRequest["role"])} className="w-full rounded-md border border-slate-700 bg-slate-900/80 px-2 py-1.5 text-xs outline-none focus:ring focus:ring-indigo-500">
                      <option value="admin">admin</option>
                      <option value="analyst">analyst</option>
                      <option value="viewer">viewer</option>
                    </select>
                    <button onClick={onCreateInvite} disabled={inviteBusy} className="rounded-md bg-cyan-600 px-2 py-1.5 text-xs font-medium text-white hover:bg-cyan-500 disabled:opacity-60">
                      {inviteBusy ? "Creating…" : "Create invite"}
                    </button>
                    {inviteError && <p className="text-xs text-rose-300">{inviteError}</p>}
                    {inviteToken && (
                      <>
                        <p className="break-all text-[10px] text-cyan-300">Token: {inviteToken}</p>
                        {inviteLink && (
                          <div className="space-y-1">
                            <a href={inviteLink} target="_blank" rel="noreferrer" className="break-all text-[10px] text-indigo-300 underline">{inviteLink}</a>
                            <div className="flex items-center gap-2">
                              <button onClick={onCopyInviteLink} className="rounded-md border border-indigo-400/40 px-2 py-1 text-[10px] text-indigo-200 hover:bg-indigo-500/20">Copy link</button>
                              {inviteExpiryLabel && <span className="text-[10px] text-slate-400">Expires: {inviteExpiryLabel}</span>}
                            </div>
                            {inviteCopied && <p className="text-[10px] text-emerald-300">{inviteCopied}</p>}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                  <div className="mb-3 space-y-2 border-t border-slate-800 pt-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="text-[11px] uppercase tracking-wide text-slate-400">Recent Invites</h4>
                        {lastAdminRefreshAt && (
                          <p className="mt-1 inline-flex items-center gap-1 text-[10px] text-emerald-300">
                            <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
                            Live · {formatDistanceToNow(new Date(lastAdminRefreshAt), { addSuffix: true })}
                          </p>
                        )}
                      </div>
                      <button onClick={onRefreshInvites} disabled={inviteListBusy} className="rounded-md border border-slate-700 px-2 py-1 text-[10px] text-slate-300 hover:bg-slate-800 disabled:opacity-60">
                        {inviteListBusy ? "Refreshing…" : "Refresh"}
                      </button>
                    </div>
                    {inviteActionMessage && <p className="text-[10px] text-slate-300">{inviteActionMessage}</p>}
                    <div className="max-h-36 space-y-2 overflow-auto pr-1">
                      {invites.length === 0 ? <p className="text-xs text-slate-500">No invites.</p> : invites.map((inv) => (
                        <div key={inv.token} className="rounded-lg border border-slate-800 bg-slate-900/50 p-2">
                          <p className="truncate text-[11px] text-slate-200">{inv.email}</p>
                          <div className="mt-1 flex items-center justify-between gap-2">
                            <p className="text-[10px] uppercase text-slate-400">{inv.role} · {inv.status}</p>
                            {inv.status === "active" && (
                              <button onClick={() => onRevokeInvite(inv.token)} disabled={revokingToken === inv.token} className="rounded-md border border-rose-400/40 px-2 py-1 text-[10px] text-rose-300 hover:bg-rose-500/20 disabled:opacity-60">
                                {revokingToken === inv.token ? "…" : "Revoke"}
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="max-h-36 space-y-2 overflow-auto pr-1">
                    {teamUsers.length === 0 ? <p className="text-xs text-slate-500">No team users yet.</p> : teamUsers.map((u) => (
                      <div key={u.id} className="rounded-lg border border-slate-800 bg-slate-900/50 p-2">
                        <p className="truncate text-[11px] text-slate-200">{u.email}</p>
                        <p className="text-[10px] uppercase text-slate-400">{u.role}</p>
                      </div>
                    ))}
                  </div>
                </article>
              </>
            )}
          </div>
        </section>

        {/* Recent Alerts table */}
        <section className="mt-6">
          <article className="terminal-panel overflow-hidden rounded-3xl">
            <div className="border-b border-slate-800/80 px-5 py-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold text-slate-100">Recent Dashboard Alerts</h2>
                  <p className="mt-1 text-[11px] text-slate-500">Fast triage table for analysts and investigators</p>
                </div>
                <span className="rounded-full border border-slate-700 bg-slate-950/70 px-3 py-1 text-[10px] uppercase tracking-[0.22em] text-slate-400">{dashboard?.alerts.length ?? 0} rows</span>
              </div>
            </div>
            <div className="overflow-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="sticky top-0 z-10 bg-slate-950/95 text-[10px] uppercase tracking-[0.22em] text-slate-500 backdrop-blur">
                  <tr>
                    <th className="px-5 py-3">Severity</th>
                    <th className="px-5 py-3">Chain</th>
                    <th className="px-5 py-3">Title</th>
                    <th className="px-5 py-3">Wallet</th>
                    <th className="px-5 py-3">Amount</th>
                    <th className="px-5 py-3">Score</th>
                    <th className="px-5 py-3">Summary</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80 text-slate-200">
                  {(dashboard?.alerts.length ?? 0) === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-5 py-8 text-center text-sm text-slate-500">
                        No dashboard alerts yet. Start with a sample wallet, run intelligence, and add the result to your watchlist to activate the alert feed.
                      </td>
                    </tr>
                  ) : dashboard?.alerts.map((alert) => (
                    <tr key={alert.id} className="group hover:bg-slate-900/50">
                      <td className="px-5 py-3">
                        <span className={cn("rounded-full border px-2 py-1 text-xs uppercase", riskTone(alert.severity))}>{alert.severity}</span>
                      </td>
                      <td className="px-5 py-3">
                        <span className="rounded-full border border-cyan-500/35 bg-cyan-500/10 px-2 py-1 text-[10px] uppercase text-cyan-200">{alert.chain}</span>
                      </td>
                      <td className="px-5 py-3 text-sm font-medium text-slate-100">{alert.title}</td>
                      <td className="px-5 py-3 font-mono text-[11px] text-slate-400">{alert.wallet}</td>
                      <td className="px-5 py-3 text-sm text-slate-300">${Intl.NumberFormat("en-US").format(alert.amount_usd)}</td>
                      <td className="px-5 py-3 text-sm font-semibold text-white">{alert.score}</td>
                      <td className="px-5 py-3 text-[12px] text-slate-300 group-hover:text-slate-200">{alert.summary}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </section>

        </>)}{/* end dashboard tab */}

        {/* ── Alerts tab ──────────────────────────────────────────────────── */}
        {activeTab === "alerts" && loggedIn && (
          <section className="mt-6 animate-fade-in-up space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-2xl font-bold text-white">Alert Management</h2>
                <p className="mt-1 text-xs text-slate-400">Full-spectrum alert triage, acknowledge, and resolution</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <select
                  value={alertsV2Filter.severity}
                  onChange={(e) => setAlertsV2Filter((f) => ({ ...f, severity: e.target.value }))}
                  aria-label="Filter by severity"
                  className="rounded-full border border-slate-700 bg-slate-900/70 px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] text-slate-300 outline-none"
                >
                  <option value="">All severities</option>
                  <option value="info">Info</option>
                  <option value="warning">Warning</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
                <select
                  value={alertsV2Filter.alert_type}
                  onChange={(e) => setAlertsV2Filter((f) => ({ ...f, alert_type: e.target.value }))}
                  aria-label="Filter by type"
                  className="rounded-full border border-slate-700 bg-slate-900/70 px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] text-slate-300 outline-none"
                >
                  <option value="">All types</option>
                  <option value="score_threshold">Score threshold</option>
                  <option value="watchlist_hit">Watchlist hit</option>
                  <option value="volume_spike">Volume spike</option>
                  <option value="risk_change">Risk change</option>
                  <option value="manual">Manual</option>
                </select>
                <button
                  onClick={() => setAlertsV2Filter((f) => ({ ...f, unacked_only: !f.unacked_only }))}
                  className={cn("command-chip", alertsV2Filter.unacked_only && "border-amber-500/50 bg-amber-500/15 text-amber-200")}
                >
                  {alertsV2Filter.unacked_only ? "Unread only ✓" : "All alerts"}
                </button>
                <button onClick={() => void refreshAlertsV2()} disabled={alertsV2Loading} className="command-chip disabled:opacity-60">
                  {alertsV2Loading ? "Loading…" : "Refresh"}
                </button>
                {alertsV2Unread > 0 && session?.role !== "viewer" && (
                  <button onClick={() => void onAckAllAlertsV2Handler()} disabled={alertsV2Loading} className="command-chip disabled:opacity-60">
                    Ack all ({alertsV2Unread})
                  </button>
                )}
              </div>
            </div>

            {alertsV2Error && <div className="rounded-2xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-xs text-rose-200">{alertsV2Error}</div>}
            {alertsV2Message && <div className="rounded-2xl border border-emerald-500/25 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-200">{alertsV2Message}</div>}

            <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
              {/* Alert feed */}
              <div className="space-y-4">
                {/* Stats strip */}
                <div className="grid grid-cols-4 gap-3">
                  <OpsMetric label="Total" value={String(alertsV2.length)} tone="indigo" />
                  <OpsMetric label="Unread" value={String(alertsV2Unread)} tone="amber" />
                  <OpsMetric label="Critical" value={String(alertsV2.filter((a) => a.severity === "critical").length)} tone="rose" />
                  <OpsMetric label="Resolved" value={String(alertsV2.filter((a) => a.resolved_at !== null).length)} tone="cyan" />
                </div>

                <article className="terminal-panel overflow-hidden rounded-3xl">
                  <div className="border-b border-slate-800/80 px-5 py-4">
                    <h3 className="text-sm font-semibold text-slate-100">Alert Feed</h3>
                  </div>
                  <div className="divide-y divide-slate-800/60">
                    {alertsV2.length === 0 ? (
                      <div className="px-5 py-10 text-center text-sm text-slate-500">
                        {alertsV2Loading ? "Loading alerts…" : "No alerts found. Try adjusting filters or run a wallet analysis."}
                      </div>
                    ) : alertsV2.map((alert) => (
                      <div
                        key={alert.id}
                        className={cn(
                          "flex items-start gap-4 px-5 py-4 transition hover:bg-slate-900/40",
                          alert.resolved_at && "opacity-50",
                          !alert.acknowledged && !alert.resolved_at && "bg-slate-900/25"
                        )}
                      >
                        {/* Severity dot */}
                        <div className="flex flex-col items-center gap-1 pt-1.5">
                          <span className={cn("h-2.5 w-2.5 rounded-full shrink-0",
                            alert.severity === "critical" ? "bg-rose-500" :
                            alert.severity === "high" ? "bg-orange-500" :
                            alert.severity === "warning" ? "bg-amber-500" : "bg-sky-400"
                          )} />
                          {!alert.acknowledged && <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-pulse" />}
                        </div>

                        {/* Content */}
                        <div className="min-w-0 flex-1 space-y-1.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-semibold text-white">{alert.title}</p>
                            {alert.resolved_at && <span className="rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[9px] uppercase text-emerald-300">resolved</span>}
                            {!alert.acknowledged && !alert.resolved_at && <span className="rounded-full border border-indigo-500/40 bg-indigo-500/15 px-2 py-0.5 text-[9px] uppercase text-indigo-200">unread</span>}
                            {alert.incident_id && <span className="rounded-full border border-violet-500/35 bg-violet-500/10 px-2 py-0.5 text-[9px] uppercase text-violet-300">inc #{alert.incident_id}</span>}
                          </div>
                          <p className="text-xs leading-relaxed text-slate-400 line-clamp-2">{alert.body}</p>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={cn("rounded-full border px-2 py-0.5 text-[9px] uppercase", riskTone(alert.risk_level))}>{alert.severity}</span>
                            <span className="rounded-full border border-slate-700 bg-slate-900/70 px-2 py-0.5 text-[9px] uppercase text-slate-300">{alert.alert_type.replace(/_/g, " ")}</span>
                            <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-[9px] uppercase text-cyan-300">{alert.chain}</span>
                            <span className="max-w-[140px] truncate font-mono text-[10px] text-slate-500">{alert.address}</span>
                            {alert.prev_score !== null && <span className="text-[9px] text-slate-600">prev {alert.prev_score}</span>}
                            <span className="ml-auto text-[9px] text-slate-600">{formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}</span>
                          </div>
                        </div>

                        {/* Actions */}
                        {session?.role !== "viewer" && !alert.resolved_at && (
                          <div className="flex shrink-0 flex-col gap-1.5">
                            {!alert.acknowledged && (
                              <button
                                onClick={() => void onAckAlertV2Handler(alert.id)}
                                className="rounded-md border border-slate-700 px-2.5 py-1 text-[10px] text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                              >✓ Ack</button>
                            )}
                            <button
                              onClick={() => void onResolveAlertHandler(alert.id)}
                              className="rounded-md border border-emerald-500/35 bg-emerald-500/10 px-2.5 py-1 text-[10px] text-emerald-300 hover:bg-emerald-500/20"
                            >Resolve</button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </article>
              </div>

              {/* Right panel: create manual alert */}
              {session?.role !== "viewer" && (
                <div className="space-y-4">
                  <article className="glass rounded-3xl p-5">
                    <div className="panel-header mb-4">
                      <span className="panel-header-icon bg-rose-500/15">
                        <AlertTriangle className="h-4 w-4 text-rose-300" />
                      </span>
                      <div>
                        <h3 className="text-sm font-semibold text-white">Create Manual Alert</h3>
                        <p className="text-[10px] text-slate-500">Analyst-initiated signal</p>
                      </div>
                    </div>
                    <div className="space-y-3">
                      <input value={manualAlertForm.title} onChange={(e) => setManualAlertForm((f) => ({ ...f, title: e.target.value }))} placeholder="Alert title" className="input-field w-full" />
                      <textarea value={manualAlertForm.body} onChange={(e) => setManualAlertForm((f) => ({ ...f, body: e.target.value }))} placeholder="Describe the risk signal in detail" className="input-field min-h-[80px] w-full resize-none" />
                      <div className="grid gap-3 sm:grid-cols-2">
                        <select aria-label="Severity" value={manualAlertForm.severity} onChange={(e) => setManualAlertForm((f) => ({ ...f, severity: e.target.value as AlertSeverity }))} className="input-field">
                          <option value="info">Info</option>
                          <option value="warning">Warning</option>
                          <option value="high">High</option>
                          <option value="critical">Critical</option>
                        </select>
                        <select aria-label="Alert type" value={manualAlertForm.alert_type} onChange={(e) => setManualAlertForm((f) => ({ ...f, alert_type: e.target.value as AlertType }))} className="input-field">
                          <option value="manual">Manual</option>
                          <option value="score_threshold">Score threshold</option>
                          <option value="watchlist_hit">Watchlist hit</option>
                          <option value="volume_spike">Volume spike</option>
                          <option value="risk_change">Risk change</option>
                        </select>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <select aria-label="Chain" value={manualAlertForm.chain} onChange={(e) => setManualAlertForm((f) => ({ ...f, chain: e.target.value as Blockchain }))} className="input-field">
                          {chainOptions.map((c) => <option key={c} value={c}>{c}</option>)}
                        </select>
                        <input type="number" value={manualAlertForm.score} min={0} max={100} onChange={(e) => setManualAlertForm((f) => ({ ...f, score: Number(e.target.value) }))} placeholder="Risk score 0–100" className="input-field" />
                      </div>
                      <input value={manualAlertForm.address} onChange={(e) => setManualAlertForm((f) => ({ ...f, address: e.target.value }))} placeholder="Wallet address" className="input-field w-full" />
                      <button type="button" onClick={() => void onCreateManualAlert()} disabled={manualAlertBusy} className="inline-flex w-full items-center justify-center rounded-2xl border border-rose-500/40 bg-rose-500/15 px-4 py-2 text-sm font-semibold text-rose-100 transition hover:bg-rose-500/20 disabled:opacity-60">
                        {manualAlertBusy ? "Creating…" : "Create alert"}
                      </button>
                    </div>
                  </article>
                </div>
              )}
            </div>
          </section>
        )}

        {/* ── Incidents tab ────────────────────────────────────────────────── */}
        {activeTab === "incidents" && loggedIn && (
          <section className="mt-6 animate-fade-in-up space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-2xl font-bold text-white">Incidents</h2>
                <p className="mt-1 text-xs text-slate-400">Group related alerts into structured incident investigations</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <select
                  value={incidentStatusFilter}
                  onChange={(e) => setIncidentStatusFilter(e.target.value as typeof incidentStatusFilter)}
                  aria-label="Filter by status"
                  className="rounded-full border border-slate-700 bg-slate-900/70 px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] text-slate-300 outline-none"
                >
                  <option value="all">All statuses</option>
                  <option value="open">Open</option>
                  <option value="investigating">Investigating</option>
                  <option value="resolved">Resolved</option>
                  <option value="closed">Closed</option>
                </select>
                <button onClick={() => void refreshIncidents()} disabled={incidentsLoading} className="command-chip disabled:opacity-60">
                  {incidentsLoading ? "Loading…" : "Refresh"}
                </button>
              </div>
            </div>

            {incidentError && <div className="rounded-2xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-xs text-rose-200">{incidentError}</div>}
            {incidentMessage && <div className="rounded-2xl border border-emerald-500/25 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-200">{incidentMessage}</div>}

            <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
              {/* Detail panel */}
              <div className="space-y-4">
                {/* Stats */}
                <div className="grid grid-cols-4 gap-3">
                  <OpsMetric label="Total" value={String(incidents.length)} tone="indigo" />
                  <OpsMetric label="Open" value={String(incidents.filter((i) => i.status === "open").length)} tone="amber" />
                  <OpsMetric label="Investigating" value={String(incidents.filter((i) => i.status === "investigating").length)} tone="rose" />
                  <OpsMetric label="Resolved" value={String(incidents.filter((i) => i.status === "resolved").length)} tone="cyan" />
                </div>

                {activeIncident ? (
                  <article className="terminal-panel rounded-3xl p-5 space-y-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={cn("rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase",
                        riskTone(activeIncident.severity === "critical" ? "critical" : activeIncident.severity === "high" ? "high" : activeIncident.severity === "warning" ? "medium" : "low")
                      )}>{activeIncident.severity}</span>
                      <span className="rounded-full border border-slate-700 bg-slate-900/70 px-2.5 py-1 text-[10px] uppercase text-slate-300">{activeIncident.status}</span>
                      <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-1 text-[10px] text-violet-300">{activeIncident.alert_count} alerts</span>
                      <span className="ml-auto text-[10px] text-slate-500">Updated {formatDistanceToNow(new Date(activeIncident.updated_at), { addSuffix: true })}</span>
                    </div>

                    <div>
                      <h3 className="text-lg font-bold text-white">{activeIncident.title}</h3>
                      <p className="mt-2 text-sm leading-relaxed text-slate-300">{activeIncident.description}</p>
                    </div>

                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
                        <p className="text-slate-500">Opened by</p>
                        <p className="mt-1 font-medium text-white truncate">{activeIncident.opened_by}</p>
                      </div>
                      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
                        <p className="text-slate-500">Assigned to</p>
                        <p className="mt-1 font-medium text-white truncate">{activeIncident.assigned_to ?? "Unassigned"}</p>
                      </div>
                    </div>

                    {session?.role !== "viewer" && (
                      <div className="flex flex-wrap gap-2">
                        {(["open", "investigating", "resolved", "closed"] as IncidentStatus[]).map((status) => (
                          <button
                            key={status}
                            type="button"
                            onClick={() => void onUpdateIncidentStatus(status)}
                            disabled={incidentBusy || activeIncident.status === status}
                            className={cn(
                              "rounded-full border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] transition",
                              activeIncident.status === status
                                ? "border-cyan-400/40 bg-cyan-500/15 text-cyan-200"
                                : "border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                            )}
                          >
                            {status}
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Linked alerts */}
                    <div>
                      <p className="mb-3 text-[10px] uppercase tracking-[0.22em] text-slate-500">Linked alerts ({activeIncident.alerts.length})</p>
                      <div className="max-h-72 space-y-2 overflow-auto pr-1">
                        {activeIncident.alerts.length === 0 ? (
                          <p className="text-xs text-slate-500">No alerts linked. Use the API to link alerts to this incident.</p>
                        ) : activeIncident.alerts.map((alert) => (
                          <div key={alert.id} className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2 space-y-1.5">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className={cn("rounded-full border px-2 py-0.5 text-[9px] uppercase", riskTone(alert.risk_level))}>{alert.severity}</span>
                              <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-[9px] uppercase text-cyan-300">{alert.chain}</span>
                              {alert.acknowledged && <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[9px] uppercase text-emerald-300">acked</span>}
                              {alert.resolved_at && <span className="rounded-full border border-slate-600 px-2 py-0.5 text-[9px] uppercase text-slate-400">resolved</span>}
                            </div>
                            <p className="text-sm font-medium text-white">{alert.title}</p>
                            <p className="font-mono text-[10px] text-slate-500 truncate">{alert.address}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </article>
                ) : (
                  <div className="terminal-panel rounded-3xl p-8 text-center text-sm text-slate-500">
                    {incidentsLoading ? "Loading incidents…" : "Select an incident or create a new one to group alerts."}
                  </div>
                )}
              </div>

              {/* Right: queue + create form */}
              <div className="space-y-4">
                {session?.role !== "viewer" && (
                  <article className="glass rounded-3xl p-5">
                    <div className="panel-header mb-4">
                      <span className="panel-header-icon bg-orange-500/15">
                        <Activity className="h-4 w-4 text-orange-300" />
                      </span>
                      <div>
                        <h3 className="text-sm font-semibold text-white">New Incident</h3>
                        <p className="text-[10px] text-slate-500">Group alerts into a structured investigation</p>
                      </div>
                    </div>
                    <div className="space-y-3">
                      <input value={incidentForm.title} onChange={(e) => setIncidentForm((f) => ({ ...f, title: e.target.value }))} placeholder="Incident title" className="input-field w-full" />
                      <textarea value={incidentForm.description} onChange={(e) => setIncidentForm((f) => ({ ...f, description: e.target.value }))} placeholder="Describe scope and initial assessment" className="input-field min-h-[72px] w-full resize-none" />
                      <select aria-label="Incident severity" value={incidentForm.severity} onChange={(e) => setIncidentForm((f) => ({ ...f, severity: e.target.value as AlertSeverity }))} className="input-field w-full">
                        <option value="info">Info</option>
                        <option value="warning">Warning</option>
                        <option value="high">High</option>
                        <option value="critical">Critical</option>
                      </select>
                      <button type="button" onClick={() => void onCreateIncidentHandler()} disabled={incidentBusy} className="inline-flex w-full items-center justify-center rounded-2xl border border-orange-500/40 bg-orange-500/15 px-4 py-2 text-sm font-semibold text-orange-100 transition hover:bg-orange-500/20 disabled:opacity-60">
                        {incidentBusy ? "Creating…" : "Create incident"}
                      </button>
                    </div>
                  </article>
                )}

                <article className="glass rounded-3xl p-5">
                  <div className="panel-header mb-4">
                    <span className="panel-header-icon bg-indigo-500/15">
                      <Zap className="h-4 w-4 text-indigo-300" />
                    </span>
                    <div>
                      <h3 className="text-sm font-semibold text-white">Incident Queue</h3>
                      <p className="text-[10px] text-slate-500">{incidents.length} total</p>
                    </div>
                  </div>
                  <div className="max-h-[500px] space-y-2 overflow-auto pr-1">
                    {incidents.length === 0 ? (
                      <p className="text-xs text-slate-500">No incidents yet. Create the first incident to start grouping alerts.</p>
                    ) : incidents.map((incident) => (
                      <button
                        key={incident.id}
                        type="button"
                        onClick={() => {
                          setSelectedIncidentId(incident.id);
                          void getIncidentDetail(incident.id).then(setActiveIncident).catch(() => {});
                        }}
                        className={cn(
                          "w-full rounded-2xl border px-3 py-3 text-left transition",
                          selectedIncidentId === incident.id
                            ? "border-cyan-500/35 bg-cyan-500/10"
                            : "border-slate-800 bg-slate-900/60 hover:border-slate-700"
                        )}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={cn("rounded-full border px-2 py-0.5 text-[9px] uppercase",
                            riskTone(incident.severity === "critical" ? "critical" : incident.severity === "high" ? "high" : incident.severity === "warning" ? "medium" : "low")
                          )}>{incident.severity}</span>
                          <span className="rounded-full border border-slate-700 px-2 py-0.5 text-[9px] uppercase text-slate-300">{incident.status}</span>
                          <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[9px] text-violet-300">{incident.alert_count} alerts</span>
                          <span className="ml-auto text-[10px] text-slate-500">#{incident.id}</span>
                        </div>
                        <p className="mt-2 text-sm font-semibold text-white truncate">{incident.title}</p>
                        <p className="mt-1 text-[10px] text-slate-500">{formatDistanceToNow(new Date(incident.created_at), { addSuffix: true })}</p>
                      </button>
                    ))}
                  </div>
                </article>
              </div>
            </div>
          </section>
        )}

        {commandPaletteOpen && loggedIn && (
          <div className="palette-overlay" onClick={() => { setCommandPaletteOpen(false); setCommandQuery(""); }}>
            <div className="palette-panel" onClick={(event) => event.stopPropagation()}>
              <div className="flex items-center gap-2 border-b border-slate-800 px-4 py-3">
                <Search className="h-4 w-4 text-slate-500" />
                <input
                  autoFocus
                  value={commandQuery}
                  onChange={(e) => setCommandQuery(e.target.value)}
                  placeholder="Search actions, workflows, or tools…"
                  className="flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
                />
                <button onClick={() => { setCommandPaletteOpen(false); setCommandQuery(""); }} className="rounded-md border border-slate-800 px-2 py-1 text-[10px] text-slate-500 hover:text-white">ESC</button>
              </div>
              <div className="max-h-80 overflow-auto p-3">
                {commandItems.length === 0 ? (
                  <p className="rounded-xl border border-slate-800 bg-slate-950/45 px-3 py-3 text-sm text-slate-500">No matching commands.</p>
                ) : commandItems.map((item) => (
                  <button
                    key={item.label}
                    onClick={() => { item.action(); setCommandPaletteOpen(false); setCommandQuery(""); }}
                    className="mb-2 flex w-full items-center justify-between rounded-xl border border-slate-800 bg-slate-950/45 px-3 py-3 text-left hover:border-indigo-500/35 hover:bg-slate-900/80"
                  >
                    <span className="text-sm font-medium text-white">{item.label}</span>
                    <span className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Run</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

      </main>
    </div>
  );
}

// ─── Cluster Graph ─────────────────────────────────────────────────────────────

function ClusterGraph({ cluster }: { cluster: WalletClusterResponse }) {
  const [expanded, setExpanded] = useState(true);
  const [hoveredNode, setHoveredNode] = useState<ClusterNode | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<ClusterEdge | null>(null);
  const [heuristicFilter, setHeuristicFilter] = useState<"all" | ClusterHeuristicEvidence["heuristic"]>("all");
  const [relationFilter, setRelationFilter] = useState<"all" | ClusterEdge["relation"]>("all");
  const [minEdgeConfidence, setMinEdgeConfidence] = useState(0);
  const W = 480, H = 220, NODE_R = 28;
  const cx = W / 2, cy = H / 2;
  const isLiveCluster = cluster.narrative.startsWith("Live Ethereum cluster built");
  const isPartialCluster = cluster.narrative.toLowerCase().includes("partially sampled");

  const relationLabel = (relation: ClusterEdge["relation"]) => relation.replace(/_/g, " ");

  const heuristicLabel = (heuristic: ClusterHeuristicEvidence["heuristic"]) => heuristic.replace(/_/g, " ");

  const scoreColor = (score: number) => {
    if (score >= 75) return "#f43f5e";
    if (score >= 50) return "#f97316";
    if (score >= 25) return "#eab308";
    return "#22c55e";
  };

  const filteredEdges = useMemo(() => {
    return cluster.edges.filter((edge) => {
      if (relationFilter !== "all" && edge.relation !== relationFilter) return false;
      if (edge.confidence < minEdgeConfidence) return false;
      if (heuristicFilter !== "all" && !edge.evidence.some((item) => item.heuristic === heuristicFilter)) return false;
      return true;
    });
  }, [cluster.edges, heuristicFilter, minEdgeConfidence, relationFilter]);

  const visibleAddresses = useMemo(() => {
    const addresses = new Set<string>([cluster.root_address]);
    filteredEdges.forEach((edge) => {
      addresses.add(edge.source);
      addresses.add(edge.target);
    });
    return addresses;
  }, [cluster.root_address, filteredEdges]);

  const filteredNodes = useMemo(() => {
    const filtered = cluster.nodes.filter((node) => node.is_root || visibleAddresses.has(node.address));
    return filtered.length > 0 ? filtered : cluster.nodes.filter((node) => node.is_root);
  }, [cluster.nodes, visibleAddresses]);

  const visibleHeuristics = useMemo(() => {
    if (heuristicFilter === "all") return cluster.heuristics;
    return cluster.heuristics.filter((item) => item.heuristic === heuristicFilter);
  }, [cluster.heuristics, heuristicFilter]);

  const strongestEdges = useMemo(() => {
    return [...cluster.edges]
      .sort((left, right) => right.confidence - left.confidence || right.strength - left.strength)
      .slice(0, 3);
  }, [cluster.edges]);

  const nodePositions = useMemo(() => {
    const pos: Record<string, { x: number; y: number }> = {};
    const nonRoot = filteredNodes.filter((n) => !n.is_root);
    filteredNodes.filter((n) => n.is_root).forEach((n) => { pos[n.address] = { x: cx, y: cy }; });
    nonRoot.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / nonRoot.length - Math.PI / 2;
      const r = Math.min(cx, cy) - NODE_R - 10;
      pos[n.address] = { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
    });
    return pos;
  }, [filteredNodes, cx, cy]);

  return (
    <div className="terminal-panel rounded-2xl p-4">
      <button onClick={() => setExpanded((v) => !v)} className="mb-2 flex w-full items-center justify-between text-xs font-medium text-slate-300 hover:text-white">
        <span className="flex items-center gap-2">
          <Globe className="h-3.5 w-3.5 text-indigo-300" />
          Wallet Cluster · {isLiveCluster ? "Live Ethereum" : `Risk ${cluster.cluster_risk}`}
          <span className="text-slate-500">({cluster.nodes.length} nodes · {cluster.confidence}% confidence)</span>
        </span>
        {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>
      {expanded && (
        <>
          <div className="mb-3 grid gap-3 sm:grid-cols-4 lg:grid-cols-5">
            <SignalPill label="Cluster ID" value={cluster.cluster_id} tone="indigo" mono />
            <SignalPill label="Source" value={isLiveCluster ? "Live on-chain" : "Heuristic"} tone="indigo" />
            <SignalPill label="Confidence" value={`${cluster.confidence}%`} tone="cyan" />
            <SignalPill label="Score" value={`${cluster.cluster_score}/100`} tone="rose" />
            <SignalPill label="Refresh" value={`${cluster.refresh_suggested_after_sec}s`} tone="amber" />
          </div>

          <div className="mb-3 flex flex-wrap items-center gap-2 rounded-2xl border border-slate-800/80 bg-slate-950/40 px-3 py-2 text-[10px] uppercase tracking-[0.18em] text-slate-400">
            <span>Updated {formatDistanceToNow(new Date(cluster.last_updated_at), { addSuffix: true })}</span>
            {cluster.cross_chain && <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-cyan-300">cross-chain</span>}
            {isLiveCluster && <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-emerald-300">direct counterparties</span>}
            {isPartialCluster && <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-amber-300">partial explorer sample</span>}
            {visibleHeuristics.slice(0, 4).map((heuristic) => (
              <span key={`${heuristic.heuristic}-${heuristic.description}`} className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-1 text-violet-200 normal-case tracking-normal">
                {heuristicLabel(heuristic.heuristic)} · {heuristic.confidence}%
              </span>
            ))}
          </div>

          <div className="mb-3 grid gap-3 rounded-2xl border border-slate-800/80 bg-slate-950/40 p-3 lg:grid-cols-[1.2fr_1fr_1fr_auto]">
            <select
              value={heuristicFilter}
              onChange={(event) => setHeuristicFilter(event.target.value as typeof heuristicFilter)}
              aria-label="Filter graph by heuristic"
              className="input-field"
            >
              <option value="all">All heuristics</option>
              {cluster.heuristics.map((item) => (
                <option key={item.heuristic} value={item.heuristic}>{heuristicLabel(item.heuristic)}</option>
              ))}
            </select>
            <select
              value={relationFilter}
              onChange={(event) => setRelationFilter(event.target.value as typeof relationFilter)}
              aria-label="Filter graph by relation"
              className="input-field"
            >
              <option value="all">All relations</option>
              {Array.from(new Set(cluster.edges.map((edge) => edge.relation))).map((relation) => (
                <option key={relation} value={relation}>{relationLabel(relation)}</option>
              ))}
            </select>
            <label className="flex flex-col justify-center rounded-xl border border-slate-800 bg-slate-950/45 px-3 py-2 text-[10px] uppercase tracking-[0.18em] text-slate-500">
              Min confidence
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={minEdgeConfidence}
                onChange={(event) => setMinEdgeConfidence(Number(event.target.value))}
                className="mt-2 accent-indigo-400"
              />
              <span className="mt-1 text-slate-300">{minEdgeConfidence}%+</span>
            </label>
            <button
              type="button"
              onClick={() => { setHeuristicFilter("all"); setRelationFilter("all"); setMinEdgeConfidence(0); }}
              className="command-chip self-center"
            >
              Reset
            </button>
          </div>

          <div className="rounded-2xl border border-slate-800/80 bg-slate-950/50 p-3">
          <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
            {filteredEdges.map((e: ClusterEdge, i: number) => {
              const s = nodePositions[e.source], t = nodePositions[e.target];
              if (!s || !t) return null;
              return (
                <g key={i} onMouseEnter={() => setHoveredEdge(e)} onMouseLeave={() => setHoveredEdge((current) => current === e ? null : current)}>
                  <line x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke={hoveredEdge === e ? "rgba(129,140,248,0.85)" : "rgba(99,102,241,0.45)"} strokeWidth={e.strength * 3.2} />
                  <text x={(s.x + t.x) / 2} y={(s.y + t.y) / 2 - 4} textAnchor="middle" fontSize={8} fill="#6366f1" opacity={0.7}>{relationLabel(e.relation)}</text>
                </g>
              );
            })}
            {filteredNodes.map((n: ClusterNode) => {
              const pos = nodePositions[n.address];
              if (!pos) return null;
              return (
                <g key={n.address} onMouseEnter={() => setHoveredNode(n)} onMouseLeave={() => setHoveredNode((current) => current?.address === n.address ? null : current)}>
                  <circle cx={pos.x} cy={pos.y} r={n.is_root ? NODE_R + 4 : NODE_R} fill={scoreColor(n.score)} opacity={0.18} />
                  <circle cx={pos.x} cy={pos.y} r={n.is_root ? NODE_R + 4 : NODE_R} fill="none" stroke={scoreColor(n.score)} strokeWidth={n.is_root ? 2.5 : 1.5} />
                  <circle cx={pos.x} cy={pos.y} r={n.is_root ? NODE_R - 7 : NODE_R - 8} fill="rgba(15,23,42,0.96)" />
                  <text x={pos.x} y={pos.y - 4} textAnchor="middle" fontSize={9} fill="white" fontWeight="600">{n.score}</text>
                  <text x={pos.x} y={pos.y + 9} textAnchor="middle" fontSize={7} fill="#94a3b8">{n.address.slice(0, 8)}…</text>
                  <text x={pos.x} y={pos.y + 19} textAnchor="middle" fontSize={7} fill="#22d3ee">{n.confidence}%</text>
                  {n.is_root && <text x={pos.x} y={pos.y + 19} textAnchor="middle" fontSize={7} fill="#818cf8">ROOT</text>}
                </g>
              );
            })}
          </svg>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <SignalPill label="Visible nodes" value={String(filteredNodes.length)} tone="indigo" />
            <SignalPill label="Visible edges" value={String(filteredEdges.length)} tone="cyan" />
            <SignalPill label="Heuristics" value={heuristicFilter === "all" ? "all" : heuristicLabel(heuristicFilter)} tone="amber" />
          </div>
          {strongestEdges.length > 0 && (
            <div className="mt-3 rounded-2xl border border-slate-800/80 bg-slate-950/45 p-3">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Top Counterparties</p>
                {isLiveCluster && <span className="text-[10px] text-emerald-300">Ranked from recent on-chain flow</span>}
              </div>
              <div className="grid gap-2 lg:grid-cols-3">
                {strongestEdges.map((edge) => (
                  <div key={`${edge.source}-${edge.target}`} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="rounded-full border border-indigo-500/25 bg-indigo-500/10 px-2 py-1 text-[10px] uppercase text-indigo-200">{relationLabel(edge.relation)}</span>
                      <span className="text-[10px] text-slate-500">{edge.confidence}% confidence</span>
                    </div>
                    <p className="mt-2 break-all font-mono text-[11px] text-slate-300">{edge.target}</p>
                    <p className="mt-2 text-[11px] text-slate-400">Strength {edge.strength.toFixed(2)} · Same entity {Math.round(edge.same_entity_likelihood * 100)}%</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          {hoveredEdge && (
            <div className="mt-3 rounded-2xl border border-indigo-500/20 bg-indigo-500/5 p-3 text-xs text-slate-300">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2 py-1 text-[10px] uppercase text-indigo-300">{relationLabel(hoveredEdge.relation)}</span>
                <span className="rounded-full border border-cyan-500/25 bg-cyan-500/10 px-2 py-1 text-[10px] uppercase text-cyan-300">{hoveredEdge.confidence}% confidence</span>
                <span className="rounded-full border border-violet-500/25 bg-violet-500/10 px-2 py-1 text-[10px] uppercase text-violet-300">{Math.round(hoveredEdge.same_entity_likelihood * 100)}% same entity</span>
              </div>
              <p className="mt-2 text-[11px] text-slate-400">Strength {hoveredEdge.strength.toFixed(2)}{hoveredEdge.shared_counterparties > 0 ? ` · ${hoveredEdge.shared_counterparties} shared counterparties` : ""}</p>
              {hoveredEdge.evidence.length > 0 && (
                <div className="mt-3 space-y-2">
                  {hoveredEdge.evidence.map((item) => (
                    <div key={`${item.heuristic}-${item.description}`} className="rounded-xl border border-slate-800 bg-slate-950/45 px-3 py-2">
                      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.16em] text-slate-500">
                        <span>{heuristicLabel(item.heuristic)}</span>
                        <span>•</span>
                        <span>{item.confidence}%</span>
                        <span>•</span>
                        <span>weight {item.weight.toFixed(2)}</span>
                      </div>
                      <p className="mt-2 text-[11px] leading-relaxed text-slate-300">{item.description}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {hoveredNode && (
            <div className="mt-3 rounded-2xl border border-slate-800/80 bg-slate-950/45 p-3 text-xs text-slate-300">
              <div className="flex flex-wrap items-center gap-2">
                <span className={cn("rounded-full border px-2 py-1 text-[10px] uppercase", riskTone(hoveredNode.risk_level))}>{hoveredNode.risk_level}</span>
                <span className="rounded-full border border-cyan-500/25 bg-cyan-500/10 px-2 py-1 text-[10px] uppercase text-cyan-300">{hoveredNode.chain}</span>
                {hoveredNode.is_root && <span className="rounded-full border border-indigo-500/25 bg-indigo-500/10 px-2 py-1 text-[10px] uppercase text-indigo-300">root node</span>}
                <span className="rounded-full border border-violet-500/25 bg-violet-500/10 px-2 py-1 text-[10px] uppercase text-violet-300">{hoveredNode.confidence}% confidence</span>
                <span className="rounded-full border border-slate-700 bg-slate-900/70 px-2 py-1 text-[10px] uppercase text-slate-300">{hoveredNode.activity_band} activity</span>
              </div>
              <p className="mt-2 break-all font-mono text-[11px] text-slate-400">{hoveredNode.address}</p>
              <p className="mt-2 text-sm font-semibold text-white">Risk score {hoveredNode.score}</p>
              <p className="mt-1 text-[11px] text-slate-400">Same-entity likelihood {Math.round(hoveredNode.entity_likelihood * 100)}%</p>
              {hoveredNode.last_active_at && <p className="mt-1 text-[11px] text-slate-500">Last active {formatDistanceToNow(new Date(hoveredNode.last_active_at), { addSuffix: true })}</p>}
              {hoveredNode.fingerprints.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {hoveredNode.fingerprints.map((fingerprint) => (
                    <span key={fingerprint} className="rounded-full border border-violet-500/25 bg-violet-500/10 px-2 py-1 text-[10px] text-violet-200">{fingerprint}</span>
                  ))}
                </div>
              )}
            </div>
          )}
          <p className="mt-3 text-[10px] leading-relaxed text-slate-400">{cluster.narrative}</p>
        </>
      )}
    </div>
  );
}

// ─── Shared components ────────────────────────────────────────────────────────

function TimelineRow({ title, body, tone }: { title: string; body: string; tone: "low" | "medium" | "high" | "critical" | "indigo" | "cyan" }) {
  const toneClass = {
    low: "bg-emerald-400",
    medium: "bg-amber-400",
    high: "bg-orange-400",
    critical: "bg-rose-400",
    indigo: "bg-indigo-400",
    cyan: "bg-cyan-400",
  }[tone];

  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <span className={cn("mt-1 h-2.5 w-2.5 rounded-full", toneClass)} />
        <span className="mt-1 h-full w-px bg-slate-800" />
      </div>
      <div className="pb-3">
        <p className="text-xs font-medium text-white">{title}</p>
        <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{body}</p>
      </div>
    </div>
  );
}

function OpsMetric({ label, value, tone }: { label: string; value: string; tone: "indigo" | "cyan" | "rose" | "amber" }) {
  const toneClasses = {
    indigo: "border-indigo-500/25 bg-indigo-500/10 text-indigo-300",
    cyan: "border-cyan-500/25 bg-cyan-500/10 text-cyan-300",
    rose: "border-rose-500/25 bg-rose-500/10 text-rose-300",
    amber: "border-amber-500/25 bg-amber-500/10 text-amber-300",
  }[tone];

  return (
    <div className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-950/45 p-3">
      <div>
        <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">{label}</p>
        <p className="mt-1 text-lg font-semibold text-white">{value}</p>
      </div>
      <span className={cn("rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase", toneClasses)}>{tone}</span>
    </div>
  );
}

function SignalPill({ label, value, tone, mono = false }: { label: string; value: string; tone: "indigo" | "cyan" | "rose" | "amber"; mono?: boolean }) {
  const toneClasses = {
    indigo: "border-indigo-500/20 bg-indigo-500/10 text-indigo-300",
    cyan: "border-cyan-500/20 bg-cyan-500/10 text-cyan-300",
    rose: "border-rose-500/20 bg-rose-500/10 text-rose-300",
    amber: "border-amber-500/20 bg-amber-500/10 text-amber-300",
  }[tone];

  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-800/80 bg-slate-950/35 px-3 py-2">
      <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <span className={cn("rounded-full border px-2.5 py-1 text-[10px] font-semibold", toneClasses, mono && "font-mono")}>{value}</span>
    </div>
  );
}

function StatCard({ title, value, icon, accent = "indigo" }: { title: string; value: string; icon: React.ReactNode; accent?: "indigo" | "amber" | "rose" | "cyan" }) {
  const iconBg: Record<string, string> = {
    indigo: "bg-indigo-500/15 text-indigo-300",
    amber:  "bg-amber-500/15  text-amber-300",
    rose:   "bg-rose-500/15   text-rose-300",
    cyan:   "bg-cyan-500/15   text-cyan-300",
  };
  return (
    <article className={cn("hover-lift rounded-2xl border p-5 backdrop-blur-md", "stat-" + accent)}>
      <div className={cn("inline-flex rounded-xl p-2.5", iconBg[accent])}>{icon}</div>
      <p className="mt-4 text-3xl font-bold tracking-tight text-white">{value}</p>
      <p className="mt-1.5 text-xs font-medium text-slate-400">{title}</p>
    </article>
  );
}

function FormInput({ label, value, onChange, type = "text" }: { label: string; value: string | number; onChange: (v: string) => void; type?: "text" | "number" }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-slate-400">{label}</span>
      <input value={value} type={type} onChange={(e) => onChange(e.target.value)} className="input-field" />
    </label>
  );
}


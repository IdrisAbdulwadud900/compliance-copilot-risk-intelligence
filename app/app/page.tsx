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
  Phone,
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
  addToWatchlist,
  analyzeWalletIntelligence,
  changePassword,
  clearAuthToken,
  createInvite,
  createTeamUser,
  createWebhook,
  deleteWebhook,
  exportAnalysesCSV,
  getAlertEvents,
  getAnalyses,
  getAuditLogs,
  getDashboard,
  getInvites,
  getSessionInfo,
  getTeamUsers,
  getWalletCluster,
  getWatchlist,
  getWebhooks,
  hasAuthToken,
  login,
  removeFromWatchlist,
  revokeInvite,
  updateAnalysisTags,
} from "@/lib/api";
import type {
  AlertEvent,
  AnalysisEntry,
  AuditEntry,
  Blockchain,
  ClusterEdge,
  ClusterNode,
  DashboardPayload,
  InviteEntry,
  LoginRequest,
  PasswordChangeRequest,
  SessionInfo,
  TeamUser,
  TeamUserCreateRequest,
  WalletClusterResponse,
  WalletInput,
  WalletIntelligenceResponse,
  WatchlistEntry,
  WebhookConfig,
  WebhookEvent,
} from "@/lib/types";
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

export default function Home() {
  // Core state
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [isMounted, setIsMounted] = useState(false);
  const [analyses, setAnalyses] = useState<AnalysisEntry[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditEntry[]>([]);
  const [teamUsers, setTeamUsers] = useState<TeamUser[]>([]);
  const [invites, setInvites] = useState<InviteEntry[]>([]);
  const [lastAdminRefreshAt, setLastAdminRefreshAt] = useState("");

  // Auth
  const [auth, setAuth] = useState<LoginRequest>({ email: "founder@demo.local", password: "ChangeMe123!" });
  const [authError, setAuthError] = useState("");
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [authMode, setAuthMode] = useState<"signin" | "signup">("signin");
  const [signupForm, setSignupForm] = useState({ email: "", phone: "" });
  const [signupBusy, setSignupBusy] = useState(false);
  const [signupMessage, setSignupMessage] = useState("");
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

  // Alerts
  const [alertEvents, setAlertEvents] = useState<AlertEvent[]>([]);
  const [alertUnread, setAlertUnread] = useState(0);
  const [alertBusy, setAlertBusy] = useState(false);
  const [showUnackedOnly, setShowUnackedOnly] = useState(false);

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

  useEffect(() => {
    setIsMounted(true);
    getDashboard().then(setDashboard);
    getAnalyses(20).then(setAnalyses);
    const loggedInNow = hasAuthToken();
    setLoggedIn(loggedInNow);
    const s = getSessionInfo();
    setSession(s);
    if (loggedInNow && s) refreshIntelPanels(s.role);
  }, [refreshIntelPanels]);

  // Auto-refresh every 15s
  useEffect(() => {
    if (!loggedIn) return;
    const iv = window.setInterval(() => {
      getAlertEvents(50)
        .then((p) => { setAlertEvents(p.items); setAlertUnread(p.unread_count); })
        .catch(() => {});
      if (session?.role === "admin") {
        Promise.all([getAuditLogs(8), getTeamUsers(), getInvites(15)])
          .then(([logs, users, pendingInvites]) => {
            setAuditLogs(logs); setTeamUsers(users); setInvites(pendingInvites);
            setLastAdminRefreshAt(new Date().toISOString());
          }).catch(() => {});
      }
    }, 15000);
    return () => window.clearInterval(iv);
  }, [loggedIn, session?.role]);

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

  // ─── Auth ──────────────────────────────────────────────────────────────────

  const onLogin = async () => {
    setIsLoggingIn(true); setAuthError("");
    try {
      await login(auth);
      setLoggedIn(true);
      const s = getSessionInfo(); setSession(s);
      const [dash, hist] = await Promise.all([getDashboard(), getAnalyses(20)]);
      setDashboard(dash); setAnalyses(hist);
      if (s) await refreshIntelPanels(s.role);
    } catch { setAuthError("Invalid email or password"); }
    finally { setIsLoggingIn(false); }
  };

  const onSignupEmail = async () => {
    if (!signupForm.email.trim()) { setSignupMessage("Email is required."); return; }
    setSignupBusy(true);
    setSignupMessage("");
    await new Promise((resolve) => window.setTimeout(resolve, 500));
    setSignupMessage("Signup request captured. Use Sign in for the demo account now.");
    setSignupBusy(false);
  };

  const onSocialSignup = (provider: "Google" | "Apple" | "Phone") => {
    setSignupMessage(`${provider} signup UI is ready. Backend OAuth/OTP hookup is next.`);
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

  const onLoadCluster = async () => {
    if (!intelligence) return;
    setLoadingCluster(true);
    try {
      const c = await getWalletCluster(intelligence.address, intelligence.chain);
      setCluster(c); setShowCluster(true);
    } catch { /* silent */ }
    finally { setLoadingCluster(false); }
  };

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

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="premium-shell min-h-screen grid-bg">
      <main className="relative z-10 mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">

        {/* Header */}
        {/* ── Top Navigation ───────────────────────────────────────────────── */}
        <header className="mb-8">
          <nav className="mb-6 flex items-center justify-between">
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
            <div className="flex items-center gap-2.5">
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
                  API key mode
                </div>
              ) : null}
            </div>
          </nav>

          {/* ── Login card — only when signed out ────────────────────────── */}
          {!loggedIn && (
            <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr] animate-fade-in-up">
              <article className="glass relative overflow-hidden rounded-3xl p-7">
                <span className="hero-orb hero-orb-indigo" />
                <span className="hero-orb hero-orb-cyan" />
                <div className="relative z-10 space-y-5">
                  <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/35 bg-indigo-500/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-indigo-300">
                    <Sparkles className="h-3.5 w-3.5" />
                    Real-time AML intelligence
                  </div>
                  <div>
                    <h2 className="text-3xl font-bold leading-tight text-white sm:text-4xl">Know wallet risk before money moves.</h2>
                    <p className="mt-3 max-w-xl text-sm leading-relaxed text-slate-300">
                      Compliance Copilot helps teams detect sanctions adjacency, mixer exposure, bridge-hop behavior, and suspicious wallet clusters in seconds.
                    </p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-2xl border border-slate-700/70 bg-slate-950/40 p-3">
                      <p className="text-2xl font-bold text-white">37ms</p>
                      <p className="text-[11px] text-slate-500">Fast scoring pipeline</p>
                    </div>
                    <div className="rounded-2xl border border-slate-700/70 bg-slate-950/40 p-3">
                      <p className="text-2xl font-bold text-white">4+</p>
                      <p className="text-[11px] text-slate-500">Behavior fingerprints</p>
                    </div>
                    <div className="rounded-2xl border border-slate-700/70 bg-slate-950/40 p-3">
                      <p className="text-2xl font-bold text-white">24/7</p>
                      <p className="text-[11px] text-slate-500">Watchlist alerting</p>
                    </div>
                  </div>
                  <ul className="grid gap-2 text-xs text-slate-300 sm:grid-cols-2">
                    <li className="inline-flex items-center gap-2"><LockKeyhole className="h-3.5 w-3.5 text-emerald-300" />Role-based access</li>
                    <li className="inline-flex items-center gap-2"><ShieldCheck className="h-3.5 w-3.5 text-indigo-300" />Risk scoring engine</li>
                    <li className="inline-flex items-center gap-2"><Globe className="h-3.5 w-3.5 text-cyan-300" />Cross-chain support</li>
                    <li className="inline-flex items-center gap-2"><Bell className="h-3.5 w-3.5 text-amber-300" />Live alert events</li>
                  </ul>
                </div>
              </article>

              <article className="glass rounded-3xl p-6 animate-scale-in">
                <div className="mb-5 flex rounded-xl border border-slate-700 bg-slate-900/60 p-1">
                  <button
                    onClick={() => { setAuthMode("signin"); setSignupMessage(""); }}
                    className={cn("flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition", authMode === "signin" ? "bg-indigo-500 text-white" : "text-slate-400 hover:text-slate-200")}
                  >
                    Sign in
                  </button>
                  <button
                    onClick={() => { setAuthMode("signup"); setAuthError(""); }}
                    className={cn("flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition", authMode === "signup" ? "bg-violet-500 text-white" : "text-slate-400 hover:text-slate-200")}
                  >
                    Sign up
                  </button>
                </div>

                {authMode === "signin" ? (
                  <div className="space-y-3.5">
                    <div>
                      <label className="mb-1.5 block text-xs font-medium text-slate-400">Email</label>
                      <input
                        value={auth.email}
                        onChange={(e) => setAuth((s) => ({ ...s, email: e.target.value }))}
                        onKeyDown={(e) => { if (e.key === "Enter") onLogin(); }}
                        placeholder="founder@demo.local"
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
                    <p className="text-center text-[10px] text-slate-600">
                      Demo: <span className="text-slate-400">founder@demo.local / ChangeMe123!</span>
                    </p>
                  </div>
                ) : (
                  <div>
                    <h3 className="text-sm font-semibold text-white">Create your workspace</h3>
                    <p className="mt-1 text-xs text-slate-500">Pick any onboarding method below.</p>

                    <div className="mt-4 space-y-2.5">
                      <label className="text-[11px] text-slate-400">Work email</label>
                      <input
                        value={signupForm.email}
                        onChange={(e) => setSignupForm((s) => ({ ...s, email: e.target.value }))}
                        placeholder="team@company.com"
                        className="input-field"
                      />
                      <label className="text-[11px] text-slate-400">Phone number</label>
                      <input
                        value={signupForm.phone}
                        onChange={(e) => setSignupForm((s) => ({ ...s, phone: e.target.value }))}
                        placeholder="+1 234 567 8901"
                        className="input-field"
                      />
                      <button
                        onClick={onSignupEmail}
                        disabled={signupBusy}
                        className="w-full rounded-xl bg-gradient-to-r from-violet-500 to-fuchsia-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-500/20 transition hover:opacity-90 active:scale-[.98] disabled:opacity-60"
                      >
                        {signupBusy ? "Submitting…" : "Sign up with email"}
                      </button>
                    </div>

                    <div className="my-4 flex items-center gap-3">
                      <span className="h-px flex-1 bg-slate-800" />
                      <span className="text-[10px] uppercase tracking-wider text-slate-600">or continue with</span>
                      <span className="h-px flex-1 bg-slate-800" />
                    </div>

                    <div className="grid gap-2 sm:grid-cols-3">
                      <button onClick={() => onSocialSignup("Google")} className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-700 bg-slate-900/70 px-2 py-2 text-xs text-slate-300 transition hover:border-slate-500 hover:text-white">
                        <Chrome className="h-3.5 w-3.5" />Google
                      </button>
                      <button onClick={() => onSocialSignup("Apple")} className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-700 bg-slate-900/70 px-2 py-2 text-xs text-slate-300 transition hover:border-slate-500 hover:text-white">
                        <Apple className="h-3.5 w-3.5" />Apple
                      </button>
                      <button onClick={() => onSocialSignup("Phone")} className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-700 bg-slate-900/70 px-2 py-2 text-xs text-slate-300 transition hover:border-slate-500 hover:text-white">
                        <Phone className="h-3.5 w-3.5" />Phone
                      </button>
                    </div>

                    {signupMessage && <p className="mt-3 text-xs text-cyan-300">{signupMessage}</p>}
                  </div>
                )}
              </article>
            </div>
          )}

          {/* ── Page title & change-password — only when signed in ──────── */}
          {loggedIn && (
            <div className="space-y-4">
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-white">Risk Intelligence Dashboard</h1>
                <p className="mt-1 text-sm text-slate-400">Behavior fingerprinting · Wallet clustering · Real-time alerts</p>
              </div>
              <details className="rounded-xl border border-slate-800/80 bg-slate-900/40 px-4 py-3">
                <summary className="cursor-pointer select-none text-xs font-medium text-slate-500 hover:text-slate-300">Change password</summary>
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
          )}
        </header>

        {/* Stat cards */}
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard accent="indigo" title="Wallets Monitored" value={`${dashboard?.total_wallets_monitored ?? "…"}`} icon={<Activity className="h-5 w-5 text-indigo-300" />} />
          <StatCard accent="amber"  title="Alerts Today"      value={`${dashboard?.alerts_today ?? "…"}`}            icon={<AlertTriangle className="h-5 w-5 text-amber-300" />} />
          <StatCard accent="rose"   title="Critical Alerts"   value={`${dashboard?.critical_alerts_today ?? "…"}`}   icon={<BadgeDollarSign className="h-5 w-5 text-rose-300" />} />
          <StatCard accent="cyan"   title="Watched Wallets"   value={`${watchlist.length}`}                           icon={<Eye className="h-5 w-5 text-cyan-300" />} />
        </section>

        {/* Charts row */}
        <section className="mt-6 grid gap-6 lg:grid-cols-[1.3fr_1fr]">
          <article className="glass rounded-2xl p-5">
            <h2 className="mb-3 text-base font-medium text-slate-100">7-Day Alert Trend</h2>
            <div className="h-52 w-full">
              {isMounted ? (
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
              ) : <div className="h-full w-full animate-pulse rounded-xl bg-slate-900/40" />}
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
            <div className="space-y-3 text-sm">
              <div>
                <label className="mb-1 block text-xs text-slate-300">Chain</label>
                <select value={walletInput.chain} onChange={(e) => setWalletInput((s) => ({ ...s, chain: e.target.value as Blockchain }))} aria-label="Select chain" className="w-full rounded-md border border-slate-700 bg-slate-900/80 px-2 py-1.5 text-xs uppercase outline-none focus:ring focus:ring-indigo-500">
                  {chainOptions.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <FormInput label="Wallet Address" value={walletInput.address} onChange={(v) => setWalletInput((s) => ({ ...s, address: v }))} />
              <FormInput label="Transactions (24h)" type="number" value={walletInput.txn_24h} onChange={(v) => setWalletInput((s) => ({ ...s, txn_24h: Number(v) || 0 }))} />
              <FormInput label="Volume USD (24h)" type="number" value={walletInput.volume_24h_usd} onChange={(v) => setWalletInput((s) => ({ ...s, volume_24h_usd: Number(v) || 0 }))} />
              <div className="grid grid-cols-3 gap-2">
                <FormInput label="Sanctions %" type="number" value={walletInput.sanctions_exposure_pct} onChange={(v) => setWalletInput((s) => ({ ...s, sanctions_exposure_pct: Number(v) || 0 }))} />
                <FormInput label="Mixer %" type="number" value={walletInput.mixer_exposure_pct} onChange={(v) => setWalletInput((s) => ({ ...s, mixer_exposure_pct: Number(v) || 0 }))} />
                <FormInput label="Bridge hops" type="number" value={walletInput.bridge_hops} onChange={(v) => setWalletInput((s) => ({ ...s, bridge_hops: Number(v) || 0 }))} />
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
                        <Globe className="h-3 w-3" />{loadingCluster ? "Loading…" : showCluster ? "Refresh Cluster" : "View Cluster"}
                      </button>
                      <button onClick={onQuickWatch} disabled={watchlistBusy} className="inline-flex items-center gap-1.5 rounded-md border border-cyan-500/40 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-200 hover:bg-cyan-500/20 disabled:opacity-60">
                        <BookmarkPlus className="h-3 w-3" />Watch
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
                  {analyses.length === 0 ? <p className="text-xs text-slate-500">No analyses yet.</p> : analyses.map((item) => (
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
              {session?.role !== "viewer" && (
                <div className="mb-3 space-y-2">
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
                {watchlist.length === 0 ? <p className="text-xs text-slate-500">No watched wallets.</p> : watchlist.map((w) => (
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
              <div className="max-h-64 space-y-2 overflow-auto pr-1">
                {visibleAlerts.length === 0 ? <p className="text-xs text-slate-500">{showUnackedOnly ? "No unread alerts." : "No alerts yet."}</p> : visibleAlerts.map((alert) => (
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
                <article className="glass rounded-2xl p-5">
                  <h2 className="mb-3 text-base font-medium text-slate-100">Audit Logs</h2>
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
                <article className="glass rounded-2xl p-5">
                  <div className="mb-3 flex items-center gap-2">
                    <Webhook className="h-4 w-4 text-violet-300" />
                    <h2 className="text-base font-medium text-slate-100">Webhooks</h2>
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
                <article className="glass rounded-2xl p-5">
                  <h2 className="mb-3 text-base font-medium text-slate-100">Team Management</h2>
                  <div className="mb-3 grid grid-cols-1 gap-2">
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
                    {teamUsers.map((u) => (
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
          <article className="glass overflow-hidden rounded-2xl">
            <div className="border-b border-slate-800/80 px-5 py-4">
              <h2 className="text-base font-medium text-slate-100">Recent Dashboard Alerts</h2>
            </div>
            <div className="overflow-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-900/50 text-xs uppercase tracking-wide text-slate-400">
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
                  {dashboard?.alerts.map((alert) => (
                    <tr key={alert.id} className="hover:bg-slate-900/35">
                      <td className="px-5 py-3">
                        <span className={cn("rounded-full border px-2 py-1 text-xs uppercase", riskTone(alert.severity))}>{alert.severity}</span>
                      </td>
                      <td className="px-5 py-3">
                        <span className="rounded-full border border-cyan-500/35 bg-cyan-500/10 px-2 py-1 text-[10px] uppercase text-cyan-200">{alert.chain}</span>
                      </td>
                      <td className="px-5 py-3">{alert.title}</td>
                      <td className="px-5 py-3 font-mono text-xs">{alert.wallet}</td>
                      <td className="px-5 py-3">${Intl.NumberFormat("en-US").format(alert.amount_usd)}</td>
                      <td className="px-5 py-3">{alert.score}</td>
                      <td className="px-5 py-3 text-slate-300">{alert.summary}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </section>

      </main>
    </div>
  );
}

// ─── Cluster Graph ─────────────────────────────────────────────────────────────

function ClusterGraph({ cluster }: { cluster: WalletClusterResponse }) {
  const [expanded, setExpanded] = useState(true);
  const W = 480, H = 220, NODE_R = 28;
  const cx = W / 2, cy = H / 2;

  const scoreColor = (score: number) => {
    if (score >= 75) return "#f43f5e";
    if (score >= 50) return "#f97316";
    if (score >= 25) return "#eab308";
    return "#22c55e";
  };

  const nodePositions = useMemo(() => {
    const pos: Record<string, { x: number; y: number }> = {};
    const nonRoot = cluster.nodes.filter((n) => !n.is_root);
    cluster.nodes.filter((n) => n.is_root).forEach((n) => { pos[n.address] = { x: cx, y: cy }; });
    nonRoot.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / nonRoot.length - Math.PI / 2;
      const r = Math.min(cx, cy) - NODE_R - 10;
      pos[n.address] = { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
    });
    return pos;
  }, [cluster.nodes, cx, cy]);

  return (
    <div className="rounded-xl border border-indigo-500/25 bg-slate-900/60 p-3">
      <button onClick={() => setExpanded((v) => !v)} className="mb-2 flex w-full items-center justify-between text-xs font-medium text-slate-300 hover:text-white">
        <span className="flex items-center gap-2">
          <Globe className="h-3.5 w-3.5 text-indigo-300" />
          Wallet Cluster · Risk {cluster.cluster_risk}
          <span className="text-slate-500">({cluster.nodes.length} nodes)</span>
        </span>
        {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>
      {expanded && (
        <>
          <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
            {cluster.edges.map((e: ClusterEdge, i: number) => {
              const s = nodePositions[e.source], t = nodePositions[e.target];
              if (!s || !t) return null;
              return (
                <g key={i}>
                  <line x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke="rgba(99,102,241,0.35)" strokeWidth={e.strength * 3} />
                  <text x={(s.x + t.x) / 2} y={(s.y + t.y) / 2 - 4} textAnchor="middle" fontSize={8} fill="#6366f1" opacity={0.7}>{e.relation}</text>
                </g>
              );
            })}
            {cluster.nodes.map((n: ClusterNode) => {
              const pos = nodePositions[n.address];
              if (!pos) return null;
              return (
                <g key={n.address}>
                  <circle cx={pos.x} cy={pos.y} r={n.is_root ? NODE_R + 4 : NODE_R} fill={scoreColor(n.score)} opacity={0.18} />
                  <circle cx={pos.x} cy={pos.y} r={n.is_root ? NODE_R + 4 : NODE_R} fill="none" stroke={scoreColor(n.score)} strokeWidth={n.is_root ? 2.5 : 1.5} />
                  <text x={pos.x} y={pos.y - 4} textAnchor="middle" fontSize={9} fill="white" fontWeight="600">{n.score}</text>
                  <text x={pos.x} y={pos.y + 9} textAnchor="middle" fontSize={7} fill="#94a3b8">{n.address.slice(0, 8)}…</text>
                  {n.is_root && <text x={pos.x} y={pos.y + 19} textAnchor="middle" fontSize={7} fill="#818cf8">ROOT</text>}
                </g>
              );
            })}
          </svg>
          <p className="mt-2 text-[10px] leading-relaxed text-slate-400">{cluster.narrative}</p>
        </>
      )}
    </div>
  );
}

// ─── Shared components ────────────────────────────────────────────────────────

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


"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { acceptInvite, getInviteStatus } from "@/lib/api";
import type { InvitePublicStatusResponse } from "@/lib/types";

export default function InvitePage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [statusLoading, setStatusLoading] = useState(false);
  const [inviteStatus, setInviteStatus] = useState<InvitePublicStatusResponse | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const tokenFromUrl = new URLSearchParams(window.location.search).get("token");
    if (tokenFromUrl) {
      setToken(tokenFromUrl);
    }
  }, []);

  useEffect(() => {
    const candidate = token.trim();
    if (candidate.length < 10) {
      setInviteStatus(null);
      return;
    }

    let cancelled = false;
    setStatusLoading(true);
    getInviteStatus(candidate)
      .then((data) => {
        if (!cancelled) {
          setInviteStatus(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setInviteStatus(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setStatusLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!token.trim()) {
      setError("Invite token is required.");
      return;
    }
    if (password.length < 10) {
      setError("Password must be at least 10 characters.");
      return;
    }
    if (inviteStatus && inviteStatus.status !== "active") {
      setError(`Invite is ${inviteStatus.status}. Request a new link from your admin.`);
      return;
    }

    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await acceptInvite(token.trim(), password);
      setMessage(`Welcome ${response.email}. Redirecting to dashboard...`);
      setTimeout(() => router.push("/"), 800);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to accept invite.";
      setError(message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#030711] text-white">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,#1e293b_0%,#030711_60%)]" />
      <div className="relative mx-auto flex min-h-screen max-w-xl items-center justify-center px-4 py-10">
        <section className="w-full rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
          <h1 className="text-2xl font-semibold">Accept team invite</h1>
          <p className="mt-2 text-sm text-slate-300">
            Set your password to activate your account and access the compliance dashboard.
          </p>

          <form className="mt-6 space-y-4" onSubmit={onSubmit}>
            <div>
              <label className="mb-1 block text-xs text-slate-300">Invite token</label>
              <input
                className="w-full rounded-xl border border-white/10 bg-[#0b1120] px-3 py-2 text-sm outline-none ring-indigo-500/40 transition focus:ring"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste invite token"
                autoComplete="off"
              />
              {statusLoading ? (
                <p className="mt-1 text-[11px] text-slate-400">Checking invite...</p>
              ) : inviteStatus ? (
                <p className="mt-1 text-[11px] text-slate-300">
                  Invite for {inviteStatus.email || "new user"} ({inviteStatus.role}) · status: {inviteStatus.status}
                </p>
              ) : null}
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-300">New password</label>
              <input
                type="password"
                className="w-full rounded-xl border border-white/10 bg-[#0b1120] px-3 py-2 text-sm outline-none ring-indigo-500/40 transition focus:ring"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Minimum 10 characters"
                autoComplete="new-password"
              />
            </div>

            {error ? <p className="text-xs text-rose-300">{error}</p> : null}
            {message ? <p className="text-xs text-emerald-300">{message}</p> : null}

            <button
              type="submit"
              disabled={busy || (inviteStatus !== null && inviteStatus.status !== "active")}
              className="w-full rounded-xl bg-indigo-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busy ? "Activating..." : "Activate account"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}

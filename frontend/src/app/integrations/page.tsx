"use client";

import useSWR from "swr";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

const ICONS: Record<string, string> = {
  zomato: "🍽️",
  whatsapp: "💬",
  google_calendar: "📅",
  google_sheets: "📊",
  email_smtp: "✉️",
  email_sendgrid: "📧",
  instagram_meta: "📸",
  crm_hubspot: "🎯",
  search_tavily: "🔍",
};

// Self-serve setup guide per provider: where the business owner gets the key.
// Keys are pasted here by the owner themselves and sent to the backend only.
const SETUP_GUIDE: Record<string, { steps: string[]; fields: { key: string; label: string; placeholder: string }[] }> = {
  email_sendgrid: {
    steps: ["app.sendgrid.com pe account banao", "Settings → API Keys → Create API Key (Full Access)", "Key yaha paste karke Save dabao"],
    fields: [{ key: "SENDGRID_API_KEY", label: "SendGrid API Key", placeholder: "SG.xxx..." }],
  },
  email_smtp: {
    steps: ["Gmail me 2-Step Verification ON karo", "myaccount.google.com me 'App passwords' search karke banao (naam: MAICOS)", "16-letter password + Gmail address yaha daalo"],
    fields: [
      { key: "SMTP_FROM", label: "Gmail address", placeholder: "you@gmail.com" },
      { key: "SMTP_APP_PASSWORD", label: "App Password (16 letters)", placeholder: "abcd efgh ijkl mnop" },
    ],
  },
  whatsapp: {
    steps: ["developers.facebook.com pe app banao (Business type)", "WhatsApp product add karo", "API Setup se phone number ID + token lo", "Dono yaha paste karo"],
    fields: [
      { key: "WHATSAPP_TOKEN", label: "WhatsApp Token", placeholder: "EAA..." },
      { key: "WHATSAPP_PHONE_ID", label: "Phone Number ID", placeholder: "123456789" },
    ],
  },
  instagram_meta: {
    steps: ["developers.facebook.com pe app banao", "Instagram Graph API product add karo", "Business account link karke access token banao", "Token yaha paste karo"],
    fields: [{ key: "META_ACCESS_TOKEN", label: "Meta Access Token", placeholder: "EAA..." }],
  },
  google_calendar: {
    steps: ["console.cloud.google.com pe project banao", "Google Calendar API Enable karo", "OAuth client JSON download karo", "Abhi JSON support jald aa raha — tab tak admin se sampark karo"],
    fields: [],
  },
  google_sheets: {
    steps: ["console.cloud.google.com pe project banao", "Google Sheets API Enable karo", "OAuth client JSON download karo", "Abhi JSON support jald aa raha — tab tak admin se sampark karo"],
    fields: [],
  },
  crm_hubspot: {
    steps: ["app.hubspot.com pe login karo", "Settings → Integrations → Private Apps → Create", "Token copy karke yaha paste karo"],
    fields: [{ key: "HUBSPOT_API_KEY", label: "HubSpot Private App Token", placeholder: "pat-..." }],
  },
  search_tavily: {
    steps: ["app.tavily.com pe signup karo (free 1000 searches)", "Dashboard se API key copy karo", "Key yaha paste karke Save dabao"],
    fields: [{ key: "SEARCH_PROVIDER_API_KEY", label: "Tavily API Key", placeholder: "tvly-..." }],
  },
  zomato: {
    steps: ["zomato.com/partners pe partner account se API access lo", "Key mile to yaha paste karo", "Note: bina official partner API ke status 'Configuration required' rahega"],
    fields: [{ key: "ZOMATO_API_KEY", label: "Zomato API Key", placeholder: "zomato key" }],
  },
  voice_twilio: {
    steps: ["twilio.com pe signup karo", "Account SID + Auth Token copy karo (Console)", "Ek Twilio phone number lo", "Teeno yaha paste karo"],
    fields: [
      { key: "TWILIO_ACCOUNT_SID", label: "Account SID", placeholder: "AC..." },
      { key: "TWILIO_AUTH_TOKEN", label: "Auth Token", placeholder: "..." },
      { key: "TWILIO_FROM_NUMBER", label: "Twilio Number", placeholder: "+1..." },
    ],
  },
  payments_razorpay: {
    steps: ["dashboard.razorpay.com pe login karo", "Settings → API Keys → Generate", "Key ID + Secret yaha paste karo"],
    fields: [
      { key: "RAZORPAY_KEY_ID", label: "Key ID", placeholder: "rzp_..." },
      { key: "RAZORPAY_KEY_SECRET", label: "Key Secret", placeholder: "..." },
    ],
  },
};

export default function IntegrationsPage() {
  const { user, openAuthModal, currentWorkspace } = useAuth();
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [openSetup, setOpenSetup] = useState<string | null>(null);
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({});

  async function handleSaveKeys(provider: string) {
    const guide = SETUP_GUIDE[provider];
    if (!guide) return;
    const creds: Record<string, string> = {};
    for (const f of guide.fields) {
      const v = (keyInputs[`${provider}:${f.key}`] || "").trim();
      if (v) creds[f.key] = v;
    }
    if (Object.keys(creds).length === 0) {
      setMsg("Pehle key paste karo, phir Save dabao.");
      return;
    }
    setBusy(provider);
    try {
      const r = await api.configureIntegration(provider, creds);
      setKeyInputs({});
      setMsg(
        r.status === "connected"
          ? `${provider} verified aur connected.`
          : `${provider} save ho gaya: ${r.detail || "Configuration required."}`,
      );
      mutate();
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(null);
    }
  }
  const { data, error, mutate, isLoading } = useSWR(
    user ? "integration-catalog" : null,
    () => api.integrationCatalog(),
  );

  async function handleConnect(provider: string) {
    setBusy(provider);
    setMsg(null);
    try {
      const r = await api.connectIntegration(provider, currentWorkspace?.name);
      setMsg(
        r.status === "connected"
          ? `${provider} connected.`
          : `${provider}: ${r.detail || "Configuration required."}`,
      );
      mutate();
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function handleDisconnect(provider: string) {
    setBusy(provider);
    try {
      await api.disconnectIntegration(provider);
      mutate();
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (!user) {
    return (
      <div className="max-w-2xl mx-auto py-12 px-4 text-center">
        <h1 className="text-2xl font-bold text-ink mb-2">Integrations</h1>
        <p className="text-sm text-muted mb-8">
          Connect authorized third-party services for this business. Sign in first.
        </p>
        <button
          onClick={() => openAuthModal("signin")}
          className="px-6 py-2.5 rounded-xl bg-accent text-bg font-semibold text-sm"
        >
          Sign in to Workspace
        </button>
      </div>
    );
  }

  const items = data?.integrations || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink flex items-center gap-2">
          <span>🔌</span>
          <span>Integrations</span>
        </h1>
        <p className="text-xs text-muted mt-0.5">
          Authorized connections for {currentWorkspace?.name || "this business"}. A website URL is
          research (Business Intel) — never a connection credential.
        </p>
      </div>

      {msg && <div className="text-xs text-muted">{msg}</div>}
      {error && <div className="text-xs text-bad">Failed to load integrations.</div>}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-44 rounded-2xl bg-white/[0.02] border border-white/5 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((t) => {
            const connected = t.status === "connected";
            const needsConfig = t.status === "configuration_required";
            return (
              <div
                key={t.provider}
                className="p-5 rounded-2xl bg-[#0e1217] border border-white/[0.08] flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-center text-lg">
                        {ICONS[t.provider] || "🔌"}
                      </div>
                      <div>
                        <h2 className="text-sm font-semibold text-ink">{t.name}</h2>
                        <span className="text-[10px] px-2 py-0.2 rounded-full bg-white/5 text-muted border border-white/5">
                          {t.auth_type}
                        </span>
                      </div>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                        connected
                          ? "bg-ok/10 text-ok border border-ok/20"
                          : needsConfig
                            ? "bg-warn/10 text-warn border border-warn/20"
                            : "bg-white/5 text-muted border border-white/10"
                      }`}
                    >
                      {connected ? "Connected" : needsConfig ? "Configuration required" : t.status}
                    </span>
                  </div>
                  <p className="text-xs text-muted mb-1">{t.description}</p>
                  {t.account && <p className="text-[11px] text-muted">Connected business: {t.account}</p>}
                  {t.detail && !connected && <p className="text-[11px] text-warn mt-1">{t.detail}</p>}
                  {t.note && <p className="text-[11px] text-muted mt-1">{t.note}</p>}
                  <div className="flex flex-wrap gap-1 mt-2">
                    {t.actions.map((op) => (
                      <span
                        key={op}
                        className="px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/[0.06] text-[10px] font-mono text-accent"
                      >
                        {op}
                      </span>
                    ))}
                  </div>
                </div>
                {openSetup === t.provider && SETUP_GUIDE[t.provider] && (
                  <div className="mt-3 p-3 rounded-xl bg-black/40 border border-white/10 space-y-2">
                    <div className="text-[11px] font-semibold text-ink">Khud setup karo:</div>
                    <ol className="text-[11px] text-muted space-y-0.5 list-decimal ml-4">
                      {SETUP_GUIDE[t.provider].steps.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ol>
                    {SETUP_GUIDE[t.provider].fields.map((f) => (
                      <div key={f.key}>
                        <div className="text-[11px] text-muted mb-1">{f.label}</div>
                        <input
                          type="password"
                          value={keyInputs[`${t.provider}:${f.key}`] || ""}
                          onChange={(e) =>
                            setKeyInputs({ ...keyInputs, [`${t.provider}:${f.key}`]: e.target.value })
                          }
                          placeholder={f.placeholder}
                          className="w-full bg-black/60 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-ink"
                        />
                      </div>
                    ))}
                    {SETUP_GUIDE[t.provider].fields.length > 0 && (
                      <button
                        onClick={() => handleSaveKeys(t.provider)}
                        disabled={busy === t.provider}
                        className="px-3 py-1.5 rounded-lg bg-ok text-bg text-xs font-semibold disabled:opacity-50"
                      >
                        {busy === t.provider ? "Saving…" : "Save Key"}
                      </button>
                    )}
                    <div className="text-[10px] text-muted">
                      Key sirf backend ko jayegi, screen pe dobara nahi dikhegi.
                    </div>
                  </div>
                )}
                <div className="flex gap-2 mt-4">
                  {connected ? (
                    <button
                      onClick={() => handleDisconnect(t.provider)}
                      disabled={busy === t.provider}
                      className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs hover:bg-white/10"
                    >
                      Disconnect
                    </button>
                  ) : (
                    <button
                      onClick={() => handleConnect(t.provider)}
                      disabled={busy === t.provider}
                      className="px-3 py-1.5 rounded-lg bg-accent text-bg text-xs font-semibold disabled:opacity-50"
                    >
                      {busy === t.provider ? "Checking…" : "Connect"}
                    </button>
                  )}
                  {SETUP_GUIDE[t.provider] && (
                    <button
                      onClick={() => setOpenSetup(openSetup === t.provider ? null : t.provider)}
                      className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs hover:bg-white/10"
                    >
                      {openSetup === t.provider ? "Close Setup" : "Setup Guide"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

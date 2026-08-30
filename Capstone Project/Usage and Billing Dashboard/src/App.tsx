import { useState, useEffect } from "react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type AppPlan = "Starter" | "Pro";

interface CustomerProfile {
  id: string;
  email: string;
  name: string;
  api_key: string;
}

interface UsageSummary {
  plan_id: string;
  plan_name: string;
  monthly_quota: number;
  units_used: number;
  percentage_used: number;
  estimated_cost_cents: number;
  current_period_start: string;
  current_period_end: string;
}

interface UsageHistoryPoint {
  date: string;
  units: number;
}

interface InvoiceRecord {
  id: string;
  period_start: string;
  period_end: string;
  total_cost_cents: number;
  status: string;
}

const C = {
  bg: "#14161B",
  surface: "#1D2028",
  surfaceHigh: "#222630",
  hover: "#252932",
  border: "#2A2D36",
  borderFaint: "#1F222A",
  text: "#E8E9ED",
  muted: "#8A8F9C",
  faint: "#4A4F5E",
  amber: "#E8A33D",
  amberHover: "#F0AF4A",
  teal: "#4FBFA8",
  red: "#EF4444",
  amberGlow: "rgba(232,163,61,0.08)",
  amberBorder: "rgba(232,163,61,0.22)",
  tealGlow: "rgba(79,191,168,0.08)",
  tealBorder: "rgba(79,191,168,0.22)",
};

const mono = "'JetBrains Mono', monospace";
const sans = "'Inter', sans-serif";

const API_BASE = "http://localhost:8000";

// --- Tick Meter ────────────────────────────────────────────────────────────────
function TickMeter({ used, limit, isWarning }: { used: number; limit: number; isWarning: boolean }) {
  const pct = Math.min(used / limit, 1);
  const accent = isWarning ? C.amber : C.teal;
  const W = 1000;
  const H = 72;
  const cy = 38;
  const fillX = pct * W;
  const ticks = 50;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }} aria-hidden>
      <line x1={0} y1={cy} x2={W} y2={cy} stroke={C.borderFaint} strokeWidth={1} />
      <line x1={0} y1={cy} x2={fillX} y2={cy} stroke={accent} strokeWidth={1} strokeOpacity={0.2} />
      {Array.from({ length: ticks + 1 }, (_, i) => {
        const x = (i / ticks) * W;
        const major = i % 5 === 0;
        const filled = x <= fillX;
        return (
          <line key={i}
            x1={x} y1={cy - (major ? 22 : 10) / 2}
            x2={x} y2={cy + (major ? 22 : 10) / 2}
            stroke={filled ? accent : C.border}
            strokeWidth={major ? 1.5 : 1}
            strokeOpacity={filled ? (major ? 1 : 0.6) : 0.3}
          />
        );
      })}
      <line x1={fillX} y1={cy - 30} x2={fillX} y2={cy + 30} stroke={accent} strokeWidth={2} />
      <circle cx={fillX} cy={cy} r={4.5} fill={accent} />
      <circle cx={fillX} cy={cy} r={10} fill={accent} fillOpacity={0.12} />
      {[0, 0.25, 0.5, 0.75, 1].map(f => (
        <text key={f} x={f === 0 ? 2 : f === 1 ? W - 2 : f * W}
          y={H - 2} textAnchor={f === 0 ? "start" : f === 1 ? "end" : "middle"}
          fontSize={9} fontFamily={mono} fill={C.faint}>
          {Math.round(f * limit).toLocaleString()}
        </text>
      ))}
    </svg>
  );
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: C.surfaceHigh, border: `1px solid ${C.border}`, borderRadius: 6, padding: "10px 16px" }}>
      <div style={{ fontFamily: mono, fontSize: 10, color: C.muted, marginBottom: 4, letterSpacing: "0.06em" }}>{label}</div>
      <div style={{ fontFamily: mono, fontSize: 16, fontWeight: 600, color: C.text }}>
        {payload[0].value.toLocaleString()}
        <span style={{ fontSize: 11, color: C.muted, fontWeight: 400, marginLeft: 5 }}>req</span>
      </div>
    </div>
  );
}

// ── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: string }) {
  return (
    <div style={{
      flex: 1,
      background: C.surface,
      border: `1px solid ${C.border}`,
      borderRadius: 10,
      padding: "22px 24px 20px",
      minWidth: 160,
    }}>
      <div style={{ fontSize: 10, fontFamily: mono, letterSpacing: "0.1em", textTransform: "uppercase", color: C.muted, marginBottom: 10 }}>
        {label}
      </div>
      <div style={{ fontFamily: mono, fontSize: 26, fontWeight: 700, letterSpacing: "-0.03em", color: accent ?? C.text, lineHeight: 1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: C.muted, marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

// ── Plan Card ────────────────────────────────────────────────────────────────
function PlanCard({
  name, price, features, current, onUpgrade, loading, buttonText,
}: {
  name: string; price: string; features: string[]; current: boolean;
  onUpgrade?: () => void; loading?: boolean; buttonText?: string;
}) {
  const isPro = name === "Pro";
  return (
    <div style={{
      flex: 1,
      background: isPro ? C.surfaceHigh : C.surface,
      border: `1px solid ${C.border}`,
      borderRadius: 10,
      padding: "28px 26px",
      display: "flex",
      flexDirection: "column",
      position: "relative",
      overflow: "hidden",
      minWidth: 280,
    }}>
      {isPro && (
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, height: 2,
          background: `linear-gradient(90deg, ${C.amber}00, ${C.amber}, ${C.amber}00)`,
        }} />
      )}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18 }}>
        <div>
          <div style={{ fontSize: 10, fontFamily: mono, letterSpacing: "0.1em", textTransform: "uppercase", color: C.muted, marginBottom: 6 }}>
            {current ? "Current Plan" : "Upgrade Options"}
          </div>
          <div style={{ fontSize: 20, fontWeight: 600, color: C.text }}>{name}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontFamily: mono, fontSize: 22, fontWeight: 700, color: C.text, lineHeight: 1 }}>{price}</div>
          <div style={{ fontSize: 10, color: C.muted, marginTop: 4 }}>per month</div>
        </div>
      </div>

      <div style={{ borderTop: `1px solid ${C.border}`, paddingTop: 18, marginBottom: 24 }}>
        {features.map(f => (
          <div key={f} style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 10 }}>
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none" style={{ flexShrink: 0 }}>
              <polyline points="2,6.5 5,9.5 11,3.5" stroke={current ? C.muted : C.teal} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span style={{ fontSize: 12, color: current ? C.muted : C.text }}>{f}</span>
          </div>
        ))}
      </div>

      {!current && (
        <button onClick={onUpgrade} disabled={loading} style={{
          marginTop: "auto",
          padding: "13px 20px",
          background: C.amber,
          color: "#14161B",
          fontSize: 13, fontWeight: 700, fontFamily: sans,
          border: "none", borderRadius: 7, cursor: loading ? "wait" : "pointer",
          opacity: loading ? 0.7 : 1,
          transition: "opacity 0.15s, background 0.15s",
        }}
          onMouseEnter={e => { if (!loading) e.currentTarget.style.background = C.amberHover; }}
          onMouseLeave={e => { if (!loading) e.currentTarget.style.background = C.amber; }}>
          {loading ? "Processing..." : (buttonText || (name === "Pro" ? "Upgrade to Pro" : "Switch to Starter"))}
        </button>
      )}

      {current && (
        <div style={{
          marginTop: "auto",
          padding: "13px 20px",
          background: C.tealGlow,
          border: `1px solid ${C.tealBorder}`,
          borderRadius: 7,
          display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
        }}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="5.5" stroke={C.teal} strokeWidth="1.2" />
            <polyline points="4,7 6.5,9.5 10,5" stroke={C.teal} strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span style={{ fontSize: 12, fontWeight: 600, color: C.teal }}>Current Active Plan</span>
        </div>
      )}
    </div>
  );
}

const safeGetLocalStorage = (key: string): string => {
  try {
    return localStorage.getItem(key) || "";
  } catch (e) {
    console.warn("localStorage access blocked by sandbox:", e);
    return "";
  }
};

const safeSetLocalStorage = (key: string, value: string) => {
  try {
    localStorage.setItem(key, value);
  } catch (e) {
    console.warn("localStorage write blocked by sandbox:", e);
  }
};

const safeRemoveLocalStorage = (key: string) => {
  try {
    localStorage.removeItem(key);
  } catch (e) {
    console.warn("localStorage remove blocked by sandbox:", e);
  }
};

// ── App ───────────────────────────────────────────────────────────────────────
export default function App() {
  const [apiKey, setApiKey] = useState<string>(() => safeGetLocalStorage("apimeter_key"));
  const [customer, setCustomer] = useState<CustomerProfile | null>(null);
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [history, setHistory] = useState<UsageHistoryPoint[]>([]);
  const [invoices, setInvoices] = useState<InvoiceRecord[]>([]);

  // Page level statuses
  const [isInitializing, setIsInitializing] = useState(true);
  const [authError, setAuthError] = useState("");
  const [simLoading, setSimLoading] = useState(false);
  const [simAlert, setSimAlert] = useState<{ type: "success" | "error"; msg: string } | null>(null);
  const [regName, setRegName] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regLoading, setRegLoading] = useState(false);
  const [upgradeLoading, setUpgradeLoading] = useState(false);
  const [revealKey, setRevealKey] = useState(false);

  // Simulator configurations
  const [simUnits, setSimUnits] = useState(50);
  const [simEndpoint, setSimEndpoint] = useState("/v1/models/predict");

  // Load dashboard data if API key exists
  useEffect(() => {
    if (!apiKey) {
      setIsInitializing(false);
      return;
    }
    
    setIsInitializing(true);
    setAuthError("");

    const loadData = async () => {
      try {
        const headers = { "Authorization": `Bearer ${apiKey}` };
        
        // 1. Fetch profile info
        const resProfile = await fetch(`${API_BASE}/v1/customers/me`, { headers });
        if (!resProfile.ok) throw new Error("Unauthorized API Key");
        const profileData = await resProfile.json();
        setCustomer(profileData);

        // 2. Fetch usage stats
        const resStats = await fetch(`${API_BASE}/v1/usage/summary`, { headers });
        if (resStats.ok) {
          const statsData = await resStats.json();
          setSummary(statsData);
        }

        // 3. Fetch daily history
        const resHistory = await fetch(`${API_BASE}/v1/usage/history`, { headers });
        if (resHistory.ok) {
          const historyData = await resHistory.json();
          // Format date tags for cleaner charting
          const formattedHistory = historyData.map((pt: any) => {
            const parts = pt.date.split("-");
            const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
            const m = months[parseInt(parts[1], 10) - 1] || "";
            const d = parts[2] || "";
            return { ...pt, dateStr: `${m} ${d}` };
          });
          setHistory(formattedHistory);
        }

        // 4. Fetch invoices
        const resInvoices = await fetch(`${API_BASE}/v1/invoices`, { headers });
        if (resInvoices.ok) {
          const invoicesData = await resInvoices.json();
          setInvoices(invoicesData);
        }
      } catch (err: any) {
        console.error(err);
        setAuthError(err.message || "Failed to load dashboard data. Please verify your connection.");
        safeRemoveLocalStorage("apimeter_key");
        setApiKey("");
      } finally {
        setIsInitializing(false);
      }
    };

    loadData();
  }, [apiKey]);

  // Connect user using pasted key
  const handleConnectKey = (keyVal: string) => {
    const trimmed = keyVal.trim();
    if (!trimmed.startsWith("sk_live_")) {
      setAuthError("Invalid API key format. Keys should start with 'sk_live_'");
      return;
    }
    safeSetLocalStorage("apimeter_key", trimmed);
    setApiKey(trimmed);
  };

  // Register a new customer
  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!regName || !regEmail) return;

    setRegLoading(true);
    setAuthError("");
    try {
      const res = await fetch(`${API_BASE}/v1/customers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: regEmail, name: regName }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Registration failed");
      }
      const data = await res.json();
      safeSetLocalStorage("apimeter_key", data.api_key);
      setApiKey(data.api_key);
    } catch (err: any) {
      setAuthError(err.message || "Registration failed");
    } finally {
      setRegLoading(false);
    }
  };

  // Create a randomized demo account instantly
  const handleCreateDemo = async () => {
    setRegLoading(true);
    setAuthError("");
    const rand = Math.floor(1000 + Math.random() * 9000);
    const demoName = `Demo Sandbox Partner ${rand}`;
    const demoEmail = `sandbox_partner_${rand}@demo.io`;

    try {
      const res = await fetch(`${API_BASE}/v1/customers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: demoEmail, name: demoName }),
      });
      if (!res.ok) throw new Error("Sandbox creation failed");
      const data = await res.json();
      
      // Inject some initial history directly using mock endpoints or log usage
      const headers = { "Authorization": `Bearer ${data.api_key}` };
      await fetch(`${API_BASE}/v1/usage`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint: "/v1/auth/login", units: 100 }),
      });
      await fetch(`${API_BASE}/v1/usage`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint: "/v1/models/predict", units: 150 }),
      });

      safeSetLocalStorage("apimeter_key", data.api_key);
      setApiKey(data.api_key);
    } catch (err: any) {
      setAuthError("Failed to auto-provision sandbox account.");
    } finally {
      setRegLoading(false);
    }
  };

  // Trigger usage log simulation
  const handleSimulateCall = async () => {
    if (!apiKey) return;
    setSimLoading(true);
    setSimAlert(null);

    try {
      const res = await fetch(`${API_BASE}/v1/usage`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          endpoint: simEndpoint,
          units: Number(simUnits),
        }),
      });

      if (res.status === 429) {
        throw new Error("Quota Exceeded! Metering engine returned HTTP 429 Rate Limit block.");
      }
      if (!res.ok) {
        throw new Error("Logging request failed.");
      }

      setSimAlert({ type: "success", msg: `Successfully logged ${simUnits} units to ${simEndpoint}` });

      // Refresh Stats
      const headers = { "Authorization": `Bearer ${apiKey}` };
      const resStats = await fetch(`${API_BASE}/v1/usage/summary`, { headers });
      if (resStats.ok) setSummary(await resStats.json());

      const resHistory = await fetch(`${API_BASE}/v1/usage/history`, { headers });
      if (resHistory.ok) {
        const historyData = await resHistory.json();
        const formattedHistory = historyData.map((pt: any) => {
          const parts = pt.date.split("-");
          const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
          return { ...pt, dateStr: `${months[parseInt(parts[1], 10) - 1] || ""} ${parts[2] || ""}` };
        });
        setHistory(formattedHistory);
      }
    } catch (err: any) {
      setSimAlert({ type: "error", msg: err.message });
    } finally {
      setSimLoading(false);
    }
  };

  // Trigger Stripe upgrade checkout session redirect
  const handleStripeUpgrade = async () => {
    if (!apiKey) return;
    setUpgradeLoading(true);
    try {
      const res = await fetch(`${API_BASE}/v1/billing/checkout`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${apiKey}` },
      });
      if (!res.ok) throw new Error("Failed to start checkout session.");
      const data = await res.json();
      if (data.checkout_url === "mock-checkout") {
        alert("Running in Sandbox Sandbox Mode (no Stripe key in .env). Automatically upgrading your account to the Pro Plan for sandbox testing!");
        // Refresh Stats
        const headers = { "Authorization": `Bearer ${apiKey}` };
        const resStats = await fetch(`${API_BASE}/v1/usage/summary`, { headers });
        if (resStats.ok) setSummary(await resStats.json());
      } else if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } catch (err: any) {
      alert(err.message || "Failed to initiate Stripe Checkout.");
    } finally {
      setUpgradeLoading(false);
    }
  };

  const handleDowngrade = async () => {
    if (!apiKey) return;
    setUpgradeLoading(true);
    try {
      const res = await fetch(`${API_BASE}/v1/billing/downgrade`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${apiKey}` },
      });
      if (!res.ok) throw new Error("Failed to downgrade subscription.");
      
      alert("Subscription downgraded to Starter (Free) Plan successfully!");
      
      // Refresh Stats
      const headers = { "Authorization": `Bearer ${apiKey}` };
      const resStats = await fetch(`${API_BASE}/v1/usage/summary`, { headers });
      if (resStats.ok) setSummary(await resStats.json());
    } catch (err: any) {
      alert(err.message || "Failed to downgrade subscription.");
    } finally {
      setUpgradeLoading(false);
    }
  };

  // Log out / clear authentication state
  const handleDisconnect = () => {
    safeRemoveLocalStorage("apimeter_key");
    setApiKey("");
    setCustomer(null);
    setSummary(null);
    setHistory([]);
    setInvoices([]);
    setAuthError("");
  };

  // Helper date formatter
  const formatDateStr = (isoString: string | undefined) => {
    if (!isoString) return "";
    const date = new Date(isoString);
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  };

  // Render Loader screen
  if (isInitializing) {
    return (
      <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", color: C.text, fontFamily: sans }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontFamily: mono, fontSize: 18, fontWeight: 700, letterSpacing: "0.1em", marginBottom: 12 }}>
            api<span style={{ color: C.teal }}>meter</span>
          </div>
          <div style={{ fontSize: 12, color: C.muted }}>Securing sandbox tunnel connections...</div>
        </div>
      </div>
    );
  }

  // Render Auth Setup screen if API key is missing
  if (!apiKey || !customer || !summary) {
    return (
      <div style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: sans, display: "flex", flexDirection: "column" }}>
        {/* Nav bar */}
        <nav style={{ borderBottom: `1px solid ${C.border}`, padding: "0 40px", display: "flex", alignItems: "center", height: 58 }}>
          <span style={{ fontFamily: mono, fontSize: 14, fontWeight: 700, letterSpacing: "0.06em" }}>
            api<span style={{ color: C.teal }}>meter</span>
          </span>
        </nav>

        {/* Auth Forms */}
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 20px" }}>
          <div style={{ maxWidth: 440, width: "100%", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: "36px 32px" }}>
            <h2 style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", margin: "0 0 8px 0" }}>Connect to Dashboard</h2>
            <p style={{ fontSize: 13, color: C.muted, margin: "0 0 28px 0", lineHeight: 1.5 }}>
              Provide your API bearer key to query real-time usage graphs and billing statistics, or bootstrap a fresh test profile.
            </p>

            {authError && (
              <div style={{ marginBottom: 24, padding: "12px 16px", background: "rgba(239,68,68,0.08)", border: `1px solid rgba(239,68,68,0.2)`, borderRadius: 6, color: C.red, fontSize: 13 }}>
                {authError}
              </div>
            )}

            {/* Pasting Key Form */}
            <div style={{ marginBottom: 24 }}>
              <label style={{ fontSize: 10, fontFamily: mono, letterSpacing: "0.08em", textTransform: "uppercase", color: C.muted, display: "block", marginBottom: 8 }}>
                Connect with Existing Key
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  type="password"
                  placeholder="sk_live_..."
                  id="connectKeyInput"
                  style={{
                    flex: 1,
                    background: C.bg,
                    border: `1px solid ${C.border}`,
                    borderRadius: 6,
                    padding: "10px 14px",
                    color: C.text,
                    fontSize: 12,
                    fontFamily: mono,
                  }}
                />
                <button
                  onClick={() => {
                    const inputEl = document.getElementById("connectKeyInput") as HTMLInputElement;
                    if (inputEl) handleConnectKey(inputEl.value);
                  }}
                  style={{
                    background: C.hover,
                    color: C.text,
                    border: `1px solid ${C.border}`,
                    borderRadius: 6,
                    padding: "0 18px",
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Connect
                </button>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "24px 0" }}>
              <div style={{ flex: 1, height: 1, background: C.borderFaint }} />
              <span style={{ fontSize: 10, fontFamily: mono, color: C.faint, textTransform: "uppercase" }}>Or</span>
              <div style={{ flex: 1, height: 1, background: C.borderFaint }} />
            </div>

            {/* Registration Form */}
            <form onSubmit={handleRegister} style={{ marginBottom: 24 }}>
              <label style={{ fontSize: 10, fontFamily: mono, letterSpacing: "0.08em", textTransform: "uppercase", color: C.muted, display: "block", marginBottom: 8 }}>
                Register New Customer account
              </label>
              <input
                type="text"
                placeholder="Full Name (e.g. Acme Corp)"
                value={regName}
                onChange={e => setRegName(e.target.value)}
                required
                style={{
                  width: "100%",
                  background: C.bg,
                  border: `1px solid ${C.border}`,
                  borderRadius: 6,
                  padding: "10px 14px",
                  color: C.text,
                  fontSize: 12,
                  marginBottom: 8,
                }}
              />
              <input
                type="email"
                placeholder="Email Address"
                value={regEmail}
                onChange={e => setRegEmail(e.target.value)}
                required
                style={{
                  width: "100%",
                  background: C.bg,
                  border: `1px solid ${C.border}`,
                  borderRadius: 6,
                  padding: "10px 14px",
                  color: C.text,
                  fontSize: 12,
                  marginBottom: 12,
                }}
              />
              <button
                type="submit"
                disabled={regLoading}
                style={{
                  width: "100%",
                  background: C.teal,
                  color: "#14161B",
                  border: "none",
                  borderRadius: 6,
                  padding: "11px 0",
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: regLoading ? "wait" : "pointer",
                  transition: "opacity 0.15s",
                  opacity: regLoading ? 0.7 : 1,
                }}
              >
                {regLoading ? "Registering..." : "Register & Connect"}
              </button>
            </form>

            <button
              onClick={handleCreateDemo}
              disabled={regLoading}
              style={{
                width: "100%",
                background: "transparent",
                color: C.amber,
                border: `1px solid ${C.amberBorder}`,
                borderRadius: 6,
                padding: "11px 0",
                fontSize: 12,
                fontWeight: 600,
                cursor: regLoading ? "wait" : "pointer",
              }}
              onMouseEnter={e => { e.currentTarget.style.background = C.amberGlow; }}
              onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
            >
              Generate Sandbox Test Profile
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Active Dashboard variables
  const isPro = summary.plan_id === "pro";
  const limit = summary.monthly_quota;
  const used = summary.units_used;
  const pct = summary.percentage_used;
  const remaining = Math.max(0, limit - used);
  const isWarning = pct >= 90;
  const accent = isWarning ? C.amber : C.teal;
  const bill = (summary.estimated_cost_cents / 100).toFixed(2);
  const formattedResetDate = formatDateStr(summary.current_period_end);

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: sans }}>
      
      {/* Nav */}
      <nav style={{
        borderBottom: `1px solid ${C.border}`,
        padding: "0 40px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        height: 58, position: "sticky", top: 0, background: C.bg, zIndex: 10,
      }}>
        <span style={{ fontFamily: mono, fontSize: 14, fontWeight: 700, letterSpacing: "0.06em" }}>
          api<span style={{ color: C.teal }}>meter</span>
        </span>
        
        <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
          <span style={{ fontSize: 11, fontFamily: mono, color: C.teal }}>
            ● Sandbox Connected
          </span>
          <button
            onClick={handleDisconnect}
            style={{
              background: "transparent",
              border: `1px solid ${C.border}`,
              borderRadius: 5,
              padding: "5px 12px",
              color: C.muted,
              fontSize: 11,
              fontWeight: 600,
              cursor: "pointer",
            }}
            onMouseEnter={e => { e.currentTarget.style.color = C.text; }}
            onMouseLeave={e => { e.currentTarget.style.color = C.muted; }}
          >
            Disconnect
          </button>
        </div>
      </nav>

      <main style={{ maxWidth: 1000, margin: "0 auto", padding: "44px 40px 100px" }}>

        {/* Page Heading */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 36, flexWrap: "wrap", gap: 12 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }}>Usage & Billing Dashboard</h1>
            <p style={{ margin: "5px 0 0", fontSize: 13, color: C.muted }}>
              Billing Cycle: {formatDateStr(summary.current_period_start)} – {formatDateStr(summary.current_period_end)} &nbsp;·&nbsp;
              <span style={{ fontFamily: mono, fontSize: 12, color: C.text }}>{customer.name}</span>
            </p>
          </div>
          <span style={{
            padding: "5px 12px", borderRadius: 5, fontSize: 10, fontFamily: mono,
            fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase",
            background: isPro ? C.tealGlow : C.surface,
            color: isPro ? C.teal : C.muted,
            border: `1px solid ${isPro ? C.tealBorder : C.border}`,
          }}>{summary.plan_name} Tier</span>
        </div>

        {/* Rate limit warning alerts */}
        {isWarning && (
          <div style={{
            marginBottom: 36,
            padding: "16px 22px",
            background: C.amberGlow,
            border: `1px solid ${C.amberBorder}`,
            borderLeft: `3px solid ${C.amber}`,
            borderRadius: 8,
          }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: C.amber, marginBottom: 4 }}>
              Alert: Usage approaching limit
            </div>
            <div style={{ fontSize: 13, color: C.muted, lineHeight: 1.6 }}>
              You've logged <span style={{ fontFamily: mono, color: C.text }}>{used.toLocaleString()}</span> of your <span style={{ fontFamily: mono, color: C.text }}>{limit.toLocaleString()}</span> units.
              Only <span style={{ fontFamily: mono, color: C.amber }}>{remaining.toLocaleString()}</span> remaining units before request paths block with <span style={{ fontFamily: mono, fontSize: 12 }}>HTTP 429</span>.
            </div>
          </div>
        )}

        {/* ── Row 1: Stat cards ── */}
        <div style={{ display: "flex", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
          <StatCard
            label="Requests units logged"
            value={used.toLocaleString()}
            sub={`of ${limit.toLocaleString()} quota`}
            accent={accent}
          />
          <StatCard
            label="Quota Remaining"
            value={remaining.toLocaleString()}
            sub={isWarning ? "Limit critical" : "Units available"}
            accent={isWarning ? C.amber : undefined}
          />
          <StatCard
            label="Estimated Bill"
            value={`$${bill}`}
            sub="accumulated charges"
          />
          <StatCard
            label="Period Ends"
            value={formattedResetDate}
            sub="scheduled rollover"
          />
        </div>

        {/* ── Row 2: Meter (full width) ── */}
        <div style={{
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 10,
          padding: "28px 32px 24px",
          marginBottom: 12,
        }}>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 22 }}>
            <div style={{ fontSize: 10, fontFamily: mono, letterSpacing: "0.1em", textTransform: "uppercase", color: C.muted }}>
              Monthly quota meter
            </div>
            <div style={{ fontFamily: mono, fontSize: 13, fontWeight: 600, color: accent, letterSpacing: "0.04em" }}>
              {pct}% used
            </div>
          </div>
          <TickMeter used={used} limit={limit} isWarning={isWarning} />
        </div>

        {/* ── Row 3: Simulator panel + Chart panel ── */}
        <div style={{ display: "flex", gap: 12, marginBottom: 12, flexWrap: "wrap", alignItems: "stretch" }}>
          
          {/* Chart */}
          <div style={{
            flex: "1 1 55%",
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: 10,
            padding: "24px 12px 16px 4px",
            minWidth: 320,
          }}>
            <div style={{ fontSize: 10, fontFamily: mono, letterSpacing: "0.1em", textTransform: "uppercase", color: C.muted, marginBottom: 16, paddingLeft: 20 }}>
              Requests Timeline History
            </div>
            {history.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={history} margin={{ top: 4, right: 24, bottom: 0, left: 8 }}>
                  <defs>
                    <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={accent} stopOpacity={0.15} />
                      <stop offset="100%" stopColor={accent} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="dateStr" tick={{ fontSize: 9, fontFamily: mono, fill: C.muted }} axisLine={{ stroke: C.border }} tickLine={false} dy={6} />
                  <YAxis tick={{ fontSize: 9, fontFamily: mono, fill: C.muted }} axisLine={false} tickLine={false} width={36} tickFormatter={v => v >= 1000 ? `${v / 1000}k` : String(v)} />
                  <Tooltip content={<ChartTooltip />} cursor={{ stroke: C.border, strokeWidth: 1 }} />
                  <Area type="monotone" dataKey="units" stroke={accent} strokeWidth={1.5} fill="url(#areaGrad)" dot={{ r: 2.5, fill: accent, strokeWidth: 0 }} activeDot={{ r: 4, fill: accent, strokeWidth: 0 }} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: 220, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, color: C.muted }}>
                No usage events recorded inside this billing cycle yet.
              </div>
            )}
          </div>

          {/* Simulator Panel */}
          <div style={{
            flex: "1 1 35%",
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: 10,
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            minWidth: 280,
          }}>
            <div style={{ fontSize: 10, fontFamily: mono, letterSpacing: "0.1em", textTransform: "uppercase", color: C.muted, marginBottom: 16 }}>
              API Request Simulator
            </div>
            <p style={{ fontSize: 12, color: C.muted, margin: "0 0 16px 0", lineHeight: 1.4 }}>
              Instantly simulate real-time API client traffic to test quota limits, cache updates, and HTTP 429 blocks.
            </p>

            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 10, color: C.muted, display: "block", marginBottom: 6 }}>Mock API Path</label>
              <select
                value={simEndpoint}
                onChange={e => setSimEndpoint(e.target.value)}
                style={{
                  width: "100%",
                  background: C.bg,
                  border: `1px solid ${C.border}`,
                  borderRadius: 6,
                  padding: "8px 10px",
                  color: C.text,
                  fontSize: 12,
                }}
              >
                <option value="/v1/models/predict">POST /v1/models/predict (Overage cost apply)</option>
                <option value="/v1/images/generate">POST /v1/images/generate</option>
                <option value="/v1/search">GET /v1/search</option>
                <option value="/v1/auth/token">POST /v1/auth/token</option>
              </select>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 10, color: C.muted, display: "block", marginBottom: 6 }}>Mock Units Weight</label>
              <input
                type="number"
                value={simUnits}
                onChange={e => setSimUnits(Number(e.target.value))}
                min={1}
                max={5000}
                style={{
                  width: "100%",
                  background: C.bg,
                  border: `1px solid ${C.border}`,
                  borderRadius: 6,
                  padding: "8px 10px",
                  color: C.text,
                  fontSize: 12,
                  fontFamily: mono,
                }}
              />
            </div>

            <button
              onClick={handleSimulateCall}
              disabled={simLoading}
              style={{
                width: "100%",
                background: C.teal,
                color: "#14161B",
                border: "none",
                borderRadius: 6,
                padding: "10px 0",
                fontSize: 12,
                fontWeight: 700,
                cursor: simLoading ? "wait" : "pointer",
                marginBottom: 12,
              }}
            >
              {simLoading ? "Logging Usage..." : "Send Request Event"}
            </button>

            {simAlert && (
              <div style={{
                padding: "10px 12px",
                background: simAlert.type === "success" ? "rgba(79,191,168,0.08)" : "rgba(239,68,68,0.08)",
                border: `1px solid ${simAlert.type === "success" ? C.tealBorder : "rgba(239,68,68,0.2)"}`,
                borderRadius: 6,
                color: simAlert.type === "success" ? C.teal : C.red,
                fontSize: 11,
                lineHeight: 1.4,
              }}>
                {simAlert.msg}
              </div>
            )}
          </div>
        </div>

        {/* ── Row 4: Plan cards side by side ── */}
        <div id="upgrade" style={{ display: "flex", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
          <PlanCard
            name="Starter"
            price="$0"
            current={!isPro}
            buttonText="Switch to Starter"
            onUpgrade={handleDowngrade}
            loading={upgradeLoading}
            features={["1,000 requests / month", "Overage costs: $0.05 / unit", "Standard Web API access"]}
          />
          <PlanCard
            name="Pro"
            price="$29"
            current={isPro}
            features={["50,000 requests / month", "Overage costs: $0.01 / unit", "Stripe Checkout Integrations", "Idempotency-Key headers security"]}
            onUpgrade={handleStripeUpgrade}
            loading={upgradeLoading}
          />
        </div>

        {/* ── Row 5: Billing history + API key details ── */}
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-start" }}>

          {/* Billing History Table */}
          <div style={{
            flex: "1 1 60%",
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: 10,
            overflow: "hidden",
            minWidth: 320,
          }}>
            <div style={{ padding: "20px 24px 16px", borderBottom: `1px solid ${C.border}` }}>
              <div style={{ fontSize: 10, fontFamily: mono, letterSpacing: "0.1em", textTransform: "uppercase", color: C.muted }}>
                Billing cycle invoice logs
              </div>
            </div>
            {invoices.length > 0 ? (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr>
                    {["Period Window", "Amount", "Status"].map(h => (
                      <th key={h} style={{
                        padding: "10px 20px", textAlign: "left",
                        fontSize: 9, fontFamily: mono, letterSpacing: "0.1em", textTransform: "uppercase",
                        color: C.faint, fontWeight: 500, borderBottom: `1px solid ${C.border}`,
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv, i) => (
                    <tr key={inv.id}
                      style={{ borderBottom: i < invoices.length - 1 ? `1px solid ${C.borderFaint}` : "none" }}
                      onMouseEnter={e => (e.currentTarget.style.background = C.hover)}
                      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                      <td style={{ padding: "13px 20px", color: C.text }}>
                        {formatDateStr(inv.period_start)} – {formatDateStr(inv.period_end)}
                      </td>
                      <td style={{ padding: "13px 20px", fontFamily: mono, fontSize: 11, color: C.text }}>
                        ${(inv.total_cost_cents / 100).toFixed(2)}
                      </td>
                      <td style={{ padding: "13px 20px" }}>
                        <span style={{
                          padding: "2px 7px", borderRadius: 3,
                          fontSize: 9, fontFamily: mono, letterSpacing: "0.07em", textTransform: "uppercase",
                          background: inv.status === "paid" ? C.tealGlow : C.amberGlow,
                          color: inv.status === "paid" ? C.teal : C.amber,
                          border: `1px solid ${inv.status === "paid" ? C.tealBorder : C.amberBorder}`,
                        }}>{inv.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ padding: "40px 24px", textAlign: "center", fontSize: 12, color: C.muted }}>
                No invoices have been finalized yet.
                <div style={{ fontSize: 11, color: C.faint, marginTop: 4 }}>
                  Invoices are automatically compiled at the end of each billing cycle by the background engine.
                </div>
              </div>
            )}
          </div>

          {/* API Key Box */}
          <div style={{ flex: "1 1 30%", display: "flex", flexDirection: "column", gap: 12, minWidth: 280 }}>
            <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: "20px 22px" }}>
              <div style={{ fontSize: 10, fontFamily: mono, letterSpacing: "0.1em", textTransform: "uppercase", color: C.muted, marginBottom: 14 }}>
                Secret API Keys
              </div>
              <div style={{
                fontFamily: mono,
                fontSize: 11,
                color: C.text,
                marginBottom: 16,
                background: C.bg,
                borderRadius: 6,
                padding: "10px 12px",
                border: `1px solid ${C.border}`,
                letterSpacing: "0.04em",
                wordBreak: "break-all",
              }}>
                {revealKey ? apiKey : `${apiKey.substring(0, 10)}••••••••••••••••••••`}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(apiKey);
                    alert("API key copied to clipboard!");
                  }}
                  style={{
                    flex: 1,
                    padding: "8px 12px",
                    background: "transparent",
                    border: `1px solid ${C.border}`,
                    borderRadius: 6, fontSize: 11,
                    color: C.muted, cursor: "pointer", fontFamily: sans,
                  }}
                  onMouseEnter={e => { e.currentTarget.style.color = C.text; e.currentTarget.style.borderColor = C.muted; }}
                  onMouseLeave={e => { e.currentTarget.style.color = C.muted; e.currentTarget.style.borderColor = C.border; }}
                >
                  Copy Key
                </button>
                <button
                  onClick={() => setRevealKey(!revealKey)}
                  style={{
                    flex: 1,
                    padding: "8px 12px",
                    background: "transparent",
                    border: `1px solid ${C.border}`,
                    borderRadius: 6, fontSize: 11,
                    color: C.muted, cursor: "pointer", fontFamily: sans,
                  }}
                  onMouseEnter={e => { e.currentTarget.style.color = C.text; e.currentTarget.style.borderColor = C.muted; }}
                  onMouseLeave={e => { e.currentTarget.style.color = C.muted; e.currentTarget.style.borderColor = C.border; }}
                >
                  {revealKey ? "Hide" : "Reveal"}
                </button>
              </div>
            </div>

            <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: "20px 22px" }}>
              <div style={{ fontSize: 10, fontFamily: mono, letterSpacing: "0.1em", textTransform: "uppercase", color: C.muted, marginBottom: 14 }}>
                Account Metadata
              </div>
              {[
                ["Profile ID", customer.id.substring(0, 8) + "..."],
                ["Email", customer.email],
                ["Server Status", "Online (200 OK)"],
              ].map(([k, v]) => (
                <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
                  <span style={{ fontSize: 11, color: C.muted }}>{k}</span>
                  <span style={{ fontFamily: mono, fontSize: 11, color: C.text, textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap", maxWidth: 160 }}>{v}</span>
                </div>
              ))}
            </div>
          </div>

        </div>

        {/* Footer */}
        <footer style={{
          marginTop: 60,
          paddingTop: 24,
          borderTop: `1px solid ${C.border}`,
          display: "flex",
          justifyContent: "space-between",
          fontSize: 11, color: C.muted,
          flexWrap: "wrap", gap: 12,
        }}>
          <span style={{ fontFamily: mono }}>apimeter © 2026</span>
          <div style={{ display: "flex", gap: 20 }}>
            {["Privacy", "Terms", "Status", "Support"].map(l => (
              <a key={l} href="#" style={{ color: C.muted, textDecoration: "none" }}
                onMouseEnter={e => (e.currentTarget.style.color = C.text)}
                onMouseLeave={e => (e.currentTarget.style.color = C.muted)}>{l}</a>
            ))}
          </div>
        </footer>
      </main>
    </div>
  );
}

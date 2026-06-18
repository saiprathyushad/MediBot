"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const DEMO_ACCOUNTS = [
  { username: "dr.mehta",     password: "doctor",            role: "Doctor",            color: "#DBEAFE", dot: "#3B82F6" },
  { username: "nurse.priya",  password: "nurse",             role: "Nurse",             color: "#D1FAE5", dot: "#10B981" },
  { username: "billing.ravi", password: "billing_executive", role: "Billing Executive", color: "#FEF9C3", dot: "#F59E0B" },
  { username: "tech.anand",   password: "technician",        role: "Technician",        color: "#FFEDD5", dot: "#F97316" },
  { username: "admin.sys",    password: "admin",             role: "Admin",             color: "#EDE9FE", dot: "#8B5CF6" },
];

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);

  const fillDemo = (u: string, p: string) => { setUsername(u); setPassword(p); setError(""); };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail ?? "Login failed"); }
      const data = await res.json();
      localStorage.setItem("medibot_token",    data.token);
      localStorage.setItem("medibot_role",     data.role);
      localStorage.setItem("medibot_username", data.username);
      router.push("/chat");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-5">

        {/* Header */}
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-3"
               style={{ background: "linear-gradient(135deg, #818CF8, #A78BFA)" }}>
            <span className="text-3xl">🏥</span>
          </div>
          <h1 className="text-3xl font-bold" style={{ color: "#4338CA" }}>MediBot</h1>
          <p className="text-sm mt-1" style={{ color: "#6B7280" }}>
            MediAssist Health Network · Internal AI Assistant
          </p>
        </div>

        {/* Login card */}
        <div className="rounded-3xl shadow-lg overflow-hidden"
             style={{ background: "white", border: "1px solid #E0E7FF" }}>

          {/* Gradient header strip */}
          <div className="h-2" style={{ background: "linear-gradient(90deg, #818CF8, #A78BFA, #6EE7B7)" }} />

          <form onSubmit={handleLogin} className="p-8 space-y-4">
            <div>
              <label className="block text-sm font-semibold mb-1.5" style={{ color: "#374151" }}>
                Username
              </label>
              <input
                type="text" value={username} onChange={e => setUsername(e.target.value)}
                required placeholder="e.g. dr.mehta"
                className="w-full rounded-xl px-4 py-2.5 text-sm outline-none transition-all"
                style={{ border: "1.5px solid #C7D2FE", background: "#F5F7FF" }}
                onFocus={e => (e.target.style.borderColor = "#818CF8")}
                onBlur={e  => (e.target.style.borderColor = "#C7D2FE")}
              />
            </div>

            <div>
              <label className="block text-sm font-semibold mb-1.5" style={{ color: "#374151" }}>
                Password
              </label>
              <input
                type="password" value={password} onChange={e => setPassword(e.target.value)}
                required placeholder="Password"
                className="w-full rounded-xl px-4 py-2.5 text-sm outline-none transition-all"
                style={{ border: "1.5px solid #C7D2FE", background: "#F5F7FF" }}
                onFocus={e => (e.target.style.borderColor = "#818CF8")}
                onBlur={e  => (e.target.style.borderColor = "#C7D2FE")}
              />
            </div>

            {error && (
              <div className="rounded-xl px-4 py-2.5 text-sm"
                   style={{ background: "#FFF1F2", color: "#BE123C", border: "1px solid #FECDD3" }}>
                {error}
              </div>
            )}

            <button
              type="submit" disabled={loading}
              className="w-full rounded-xl py-2.5 text-sm font-bold text-white transition-all"
              style={{ background: "linear-gradient(135deg, #818CF8, #A78BFA)" }}
            >
              {loading ? "Signing in…" : "Sign In →"}
            </button>
          </form>
        </div>

        {/* Demo accounts */}
        <div className="rounded-3xl shadow-sm p-6"
             style={{ background: "white", border: "1px solid #E0E7FF" }}>
          <p className="text-xs font-bold uppercase tracking-widest mb-4" style={{ color: "#9CA3AF" }}>
            Demo Accounts — click to fill
          </p>
          <div className="space-y-2">
            {DEMO_ACCOUNTS.map(acct => (
              <div
                key={acct.username}
                onClick={() => fillDemo(acct.username, acct.password)}
                className="flex items-center gap-3 rounded-xl px-4 py-2.5 cursor-pointer transition-all"
                style={{ background: acct.color, border: `1px solid ${acct.dot}22` }}
                onMouseEnter={e => (e.currentTarget.style.opacity = "0.8")}
                onMouseLeave={e => (e.currentTarget.style.opacity = "1")}
              >
                <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: acct.dot }} />
                <span className="text-sm font-semibold flex-1" style={{ color: "#374151" }}>{acct.role}</span>
                <span className="text-xs font-mono" style={{ color: "#6B7280" }}>{acct.username}</span>
                <span className="text-xs font-mono" style={{ color: "#9CA3AF" }}>/ {acct.password}</span>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}

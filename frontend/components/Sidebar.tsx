"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const ROLE_STYLE: Record<string, { bg: string; text: string; border: string }> = {
  doctor:            { bg: "#DBEAFE", text: "#1D4ED8", border: "#BFDBFE" },
  nurse:             { bg: "#D1FAE5", text: "#065F46", border: "#A7F3D0" },
  billing_executive: { bg: "#FEF9C3", text: "#92400E", border: "#FDE68A" },
  technician:        { bg: "#FFEDD5", text: "#9A3412", border: "#FED7AA" },
  admin:             { bg: "#EDE9FE", text: "#5B21B6", border: "#DDD6FE" },
};

const ROLE_LABELS: Record<string, string> = {
  doctor:            "Doctor",
  nurse:             "Nurse",
  billing_executive: "Billing Executive",
  technician:        "Technician",
  admin:             "Admin",
};

const COLLECTION_CONFIG: Record<string, { icon: string; bg: string; text: string }> = {
  general:   { icon: "📋", bg: "#F0F4FF", text: "#4338CA" },
  clinical:  { icon: "🩺", bg: "#EFF6FF", text: "#1D4ED8" },
  nursing:   { icon: "💉", bg: "#F0FDF4", text: "#065F46" },
  billing:   { icon: "🧾", bg: "#FEFCE8", text: "#92400E" },
  equipment: { icon: "🔧", bg: "#FFF7ED", text: "#9A3412" },
};

interface SidebarProps {
  role: string;
  username: string;
  onLogout: () => void;
}

export default function Sidebar({ role, username, onLogout }: SidebarProps) {
  const [collections, setCollections] = useState<string[]>([]);

  useEffect(() => {
    if (!role) return;
    fetch(`${API_BASE}/collections/${role}`)
      .then(r => r.json())
      .then(d => setCollections(d.collections ?? []))
      .catch(() => setCollections([]));
  }, [role]);

  const roleStyle = ROLE_STYLE[role] ?? { bg: "#F3F4F6", text: "#374151", border: "#E5E7EB" };

  return (
    <aside className="w-64 flex-shrink-0 flex flex-col h-full"
           style={{ background: "white", borderRight: "1.5px solid #E0E7FF" }}>

      {/* Logo */}
      <div className="px-5 py-5" style={{ borderBottom: "1px solid #EEF2FF" }}>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center text-lg"
               style={{ background: "linear-gradient(135deg, #818CF8, #A78BFA)" }}>
            🏥
          </div>
          <div>
            <h1 className="font-bold text-base" style={{ color: "#4338CA" }}>MediBot</h1>
            <p className="text-xs" style={{ color: "#9CA3AF" }}>MediAssist Network</p>
          </div>
        </div>
      </div>

      {/* User info */}
      <div className="px-5 py-4" style={{ borderBottom: "1px solid #EEF2FF" }}>
        <p className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: "#9CA3AF" }}>
          Signed in as
        </p>
        <p className="text-sm font-semibold mb-2.5" style={{ color: "#374151" }}>
          {username}
        </p>
        <span
          className="inline-block text-xs font-bold px-3 py-1 rounded-full"
          style={{ background: roleStyle.bg, color: roleStyle.text, border: `1px solid ${roleStyle.border}` }}
        >
          {ROLE_LABELS[role] ?? role}
        </span>
      </div>

      {/* Collections */}
      <div className="px-5 py-4 flex-1">
        <p className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: "#9CA3AF" }}>
          Accessible Collections
        </p>
        <div className="space-y-2">
          {collections.map(col => {
            const cfg = COLLECTION_CONFIG[col] ?? { icon: "📄", bg: "#F9FAFB", text: "#374151" };
            return (
              <div key={col}
                   className="flex items-center gap-2.5 rounded-xl px-3 py-2"
                   style={{ background: cfg.bg }}>
                <span className="text-base">{cfg.icon}</span>
                <span className="text-sm font-medium capitalize" style={{ color: cfg.text }}>
                  {col}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Logout */}
      <div className="px-5 py-4" style={{ borderTop: "1px solid #EEF2FF" }}>
        <button
          onClick={onLogout}
          className="w-full text-sm rounded-xl py-2 font-medium transition-all"
          style={{ color: "#6B7280", background: "#F9FAFB", border: "1px solid #E5E7EB" }}
          onMouseEnter={e => {
            e.currentTarget.style.color = "#BE123C";
            e.currentTarget.style.background = "#FFF1F2";
            e.currentTarget.style.borderColor = "#FECDD3";
          }}
          onMouseLeave={e => {
            e.currentTarget.style.color = "#6B7280";
            e.currentTarget.style.background = "#F9FAFB";
            e.currentTarget.style.borderColor = "#E5E7EB";
          }}
        >
          ← Sign out
        </button>
      </div>

    </aside>
  );
}

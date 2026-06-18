"use client";

/**
 * Chat page — the main interface after login.
 *
 * Layout:
 *   - Sidebar (left): role badge, accessible collections, logout
 *   - Chat area (right): message history + input bar
 *
 * On each user message the page calls POST /chat with the Bearer token.
 * The response includes the answer, sources, retrieval_type, and role.
 * An RBAC-blocked response (zero sources + the backend refusal message)
 * is displayed as a styled warning card.
 *
 * If no token is found in localStorage the user is redirected back to login.
 */

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import MessageBubble from "@/components/MessageBubble";
import ChatInput from "@/components/ChatInput";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Fallback phrase check in case the backend rbac_blocked field is missing.
const RBAC_PHRASES = [
  "you don't have access",
  "you do not have access",
  "only answer questions from",
  "can only answer from",
];

interface Source {
  source_document: string;
  section_title: string;
  collection: string;
}

interface ChatMessage {
  role: "user" | "bot";
  text: string;
  retrieval_type?: string;
  sources?: Source[];
  is_rbac_blocked?: boolean;
}

function isRbacBlocked(answer: string, sources: Source[], backendFlag?: boolean): boolean {
  // Trust the backend flag first (most accurate).
  if (backendFlag === true) return true;
  // Fallback: phrase-based detection for older responses.
  const lower = answer.toLowerCase();
  return RBAC_PHRASES.some((phrase) => lower.includes(phrase));
}

export default function ChatPage() {
  const router = useRouter();
  const bottomRef = useRef<HTMLDivElement>(null);

  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<string>("");
  const [username, setUsername] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);

  // Load auth state from localStorage. Redirect to login if absent.
  useEffect(() => {
    const t = localStorage.getItem("medibot_token");
    const r = localStorage.getItem("medibot_role");
    const u = localStorage.getItem("medibot_username");
    if (!t || !r) {
      router.replace("/");
      return;
    }
    setToken(t);
    setRole(r);
    setUsername(u ?? "");

    // Show a welcome message when the chat first loads.
    setMessages([
      {
        role: "bot",
        text: `Hello! I'm MediBot, your MediAssist knowledge assistant. You're signed in as a ${
          r.replace("_", " ")
        }. How can I help you today?`,
        retrieval_type: undefined,
        sources: [],
      },
    ]);
  }, [router]);

  // Auto-scroll to the latest message whenever messages update.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleLogout = () => {
    localStorage.clear();
    router.replace("/");
  };

  const handleSend = async (text: string) => {
    if (!token) return;

    // Add the user's message to the chat immediately (optimistic UI).
    const userMsg: ChatMessage = { role: "user", text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ question: text }),
      });

      if (res.status === 401) {
        // Token expired — send back to login.
        localStorage.clear();
        router.replace("/");
        return;
      }

      if (!res.ok) {
        throw new Error(`Server error: ${res.status}`);
      }

      const data = await res.json();
      const blocked = isRbacBlocked(data.answer, data.sources ?? [], data.rbac_blocked);

      const botMsg: ChatMessage = {
        role: "bot",
        text: data.answer,
        retrieval_type: data.retrieval_type,
        sources: data.sources ?? [],
        is_rbac_blocked: blocked,
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      const errMsg: ChatMessage = {
        role: "bot",
        text: "Sorry, I encountered an error. Please check that the backend is running and try again.",
        sources: [],
      };
      setMessages((prev) => [...prev, errMsg]);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Show a loading state while auth is being resolved.
  if (!token) {
    return (
      <div className="flex h-full items-center justify-center text-gray-400 text-sm">
        Loading…
      </div>
    );
  }

  return (
    <div className="flex h-full">

      {/* Left sidebar */}
      <Sidebar role={role} username={username} onLogout={handleLogout} />

      {/* Main chat area */}
      <div className="flex flex-col flex-1 h-full overflow-hidden"
           style={{ background: "linear-gradient(135deg, #f0f4ff 0%, #faf5ff 60%, #f0fdf4 100%)" }}>

        {/* Scrollable message list */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
          {messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} />
          ))}

          {/* Typing indicator while waiting for the bot */}
          {loading && (
            <div className="flex justify-start">
              <div className="rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm"
                   style={{ background: "white", border: "1.5px solid #E0E7FF" }}>
                <div className="flex gap-1.5 items-center">
                  <span className="w-2 h-2 rounded-full animate-bounce [animation-delay:-0.3s]"
                        style={{ background: "#A5B4FC" }} />
                  <span className="w-2 h-2 rounded-full animate-bounce [animation-delay:-0.15s]"
                        style={{ background: "#C4B5FD" }} />
                  <span className="w-2 h-2 rounded-full animate-bounce"
                        style={{ background: "#6EE7B7" }} />
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Fixed input bar at the bottom */}
        <div className="px-6 pb-6">
          <ChatInput onSend={handleSend} disabled={loading} />
        </div>

      </div>
    </div>
  );
}

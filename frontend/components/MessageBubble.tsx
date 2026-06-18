"use client";

import { useState } from "react";

interface Source {
  source_document: string;
  section_title: string;
  collection: string;
}

interface Message {
  role: "user" | "bot";
  text: string;
  retrieval_type?: string;
  sources?: Source[];
  is_rbac_blocked?: boolean;
}

interface MessageBubbleProps { message: Message; }

const COLLECTION_DOT: Record<string, string> = {
  general:   "#818CF8",
  clinical:  "#3B82F6",
  nursing:   "#10B981",
  billing:   "#F59E0B",
  equipment: "#F97316",
};

export default function MessageBubble({ message }: MessageBubbleProps) {
  const [showSources, setShowSources] = useState(false);

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div
          className="max-w-xl rounded-2xl rounded-tr-sm px-4 py-3 text-sm shadow-sm"
          style={{
            background: "linear-gradient(135deg, #818CF8, #A78BFA)",
            color: "white",
          }}
        >
          {message.text}
        </div>
      </div>
    );
  }

  const hasSources = message.sources && message.sources.length > 0;

  // RBAC blocked — rose warning card
  if (message.is_rbac_blocked) {
    return (
      <div className="flex justify-start">
        <div
          className="max-w-2xl rounded-2xl rounded-tl-sm px-4 py-3"
          style={{ background: "#FFF1F2", border: "1.5px solid #FECDD3" }}
        >
          <div className="flex items-start gap-2.5">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
              style={{ background: "#FFE4E6" }}
            >
              🔒
            </div>
            <p className="text-sm" style={{ color: "#9F1239" }}>{message.text}</p>
          </div>
        </div>
      </div>
    );
  }

  // Normal bot message
  return (
    <div className="flex justify-start">
      <div className="max-w-2xl w-full space-y-2">
        <div
          className="rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm space-y-3"
          style={{ background: "white", border: "1.5px solid #E0E7FF" }}
        >
          {/* Answer */}
          <p className="text-sm whitespace-pre-wrap" style={{ color: "#1E293B" }}>
            {message.text}
          </p>

          {/* Footer */}
          <div
            className="flex items-center justify-between pt-2"
            style={{ borderTop: "1px solid #EEF2FF" }}
          >
            <div className="flex items-center gap-2">
              {message.retrieval_type === "hybrid_rag" && (
                <span
                  className="text-xs font-bold px-2.5 py-0.5 rounded-full"
                  style={{ background: "#DBEAFE", color: "#1D4ED8" }}
                >
                  ✦ Hybrid RAG
                </span>
              )}
              {message.retrieval_type === "sql_rag" && (
                <span
                  className="text-xs font-bold px-2.5 py-0.5 rounded-full"
                  style={{ background: "#EDE9FE", color: "#5B21B6" }}
                >
                  ⬡ SQL RAG
                </span>
              )}
            </div>

            {hasSources && (
              <button
                onClick={() => setShowSources(!showSources)}
                className="text-xs font-medium transition-colors"
                style={{ color: "#818CF8" }}
              >
                {showSources ? "Hide sources ▲" : `Sources (${message.sources!.length}) ▼`}
              </button>
            )}
          </div>

          {/* Source citations */}
          {showSources && hasSources && (
            <div className="space-y-1.5 pt-1">
              {message.sources!.map((src, i) => {
                const dot = COLLECTION_DOT[src.collection] ?? "#9CA3AF";
                return (
                  <div
                    key={i}
                    className="flex items-start gap-2.5 rounded-xl px-3 py-2 text-xs"
                    style={{ background: "#F5F7FF", border: "1px solid #E0E7FF" }}
                  >
                    <div
                      className="w-2 h-2 rounded-full flex-shrink-0 mt-0.5"
                      style={{ background: dot }}
                    />
                    <div>
                      <span className="font-semibold" style={{ color: "#374151" }}>
                        {src.source_document}
                      </span>
                      {src.section_title && (
                        <span style={{ color: "#6B7280" }}> · {src.section_title}</span>
                      )}
                      <span
                        className="ml-2 font-medium capitalize px-1.5 py-0.5 rounded-full"
                        style={{ background: "#EEF2FF", color: "#4338CA" }}
                      >
                        {src.collection}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

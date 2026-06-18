"use client";

import { useState } from "react";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState("");
  const [focused, setFocused] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-end gap-3 rounded-2xl px-4 py-3 transition-all"
      style={{
        background: "white",
        border: `1.5px solid ${focused ? "#818CF8" : "#E0E7FF"}`,
        boxShadow: focused ? "0 0 0 3px #EEF2FF" : "0 1px 4px rgba(0,0,0,0.06)",
      }}
    >
      <textarea
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        disabled={disabled}
        placeholder="Ask MediBot a question…"
        rows={1}
        className="flex-1 resize-none text-sm outline-none disabled:opacity-50 max-h-32 overflow-y-auto"
        style={{ color: "#1E293B", background: "transparent" }}
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="flex-shrink-0 rounded-xl px-4 py-2 text-sm font-bold text-white transition-all disabled:opacity-40"
        style={{ background: "linear-gradient(135deg, #818CF8, #A78BFA)" }}
      >
        {disabled ? "…" : "Send →"}
      </button>
    </form>
  );
}

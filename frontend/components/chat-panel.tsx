"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function ChatPanel({ threadId }: { threadId: string }) {
  const [messages, setMessages] = useState<{ role: "you" | "finch"; text: string }[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send() {
    const q = input.trim();
    if (!q || busy) return;
    setMessages((m) => [...m, { role: "you", text: q }]);
    setInput("");
    setBusy(true);
    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: threadId, message: q }),
      });
      const data = await r.json();
      setMessages((m) => [...m, { role: "finch", text: data.answer ?? "No answer." }]);
    } catch {
      setMessages((m) => [...m, { role: "finch", text: "Something went wrong answering that." }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="max-h-64 space-y-2 overflow-y-auto">
        {messages.map((m, i) => (
          <p key={i} className={m.role === "you" ? "text-right" : ""}>
            <span
              className={
                m.role === "you"
                  ? "inline-block rounded-lg bg-gray-900 px-3 py-1.5 text-sm text-white"
                  : "inline-block rounded-lg bg-gray-100 px-3 py-1.5 text-sm text-gray-800"
              }
            >
              {m.text}
            </span>
          </p>
        ))}
      </div>
      <div className="flex gap-2">
        <Input
          value={input}
          placeholder="Ask about the report…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <Button onClick={send} disabled={busy}>
          Ask
        </Button>
      </div>
    </div>
  );
}

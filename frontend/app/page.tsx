"use client";

import { useRef, useState } from "react";

import { ChatPanel } from "@/components/chat-panel";
import { ReportTable } from "@/components/report-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { CitationUnit, StreamEvent, UnitResult } from "@/lib/types";

export default function Home() {
  const [text, setText] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [units, setUnits] = useState<CitationUnit[]>([]);
  const [results, setResults] = useState<Record<number, UnitResult>>({});
  const [warnings, setWarnings] = useState<string[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function verify() {
    setBusy(true);
    setError(null);
    setUnits([]);
    setResults({});
    setWarnings([]);
    setDone(false);
    setThreadId(null);
    const form = new FormData();
    const file = fileRef.current?.files?.[0];
    if (file) form.append("file", file);
    if (text.trim()) form.append("text", text);
    try {
      const res = await fetch("/api/verify", { method: "POST", body: form });
      if (!res.ok || !res.body) {
        let msg = "Verification failed.";
        try {
          const j = await res.json();
          if (j?.detail) msg = j.detail;
        } catch {}
        setError(msg);
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done: eof } = await reader.read();
        if (eof) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          const ev = JSON.parse(line) as StreamEvent;
          if (ev.type === "start") setThreadId(ev.thread_id);
          if (ev.type === "units") {
            setUnits(ev.units);
            setWarnings(ev.warnings);
          }
          if (ev.type === "result") setResults((r) => ({ ...r, [ev.result.unit_id]: ev.result }));
          if (ev.type === "done") setDone(true);
        }
      }
    } catch {
      setError("Connection lost during verification.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 text-gray-900">
      <div className="mx-auto max-w-3xl space-y-6 p-4 sm:p-8">
        <div>
          <h1 className="text-3xl font-semibold">Finch</h1>
          <p className="text-gray-500">Verify every citation, quote, and holding in a legal brief before you file.</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Brief</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea rows={8} placeholder="Paste brief text…" value={text} onChange={(e) => setText(e.target.value)} />
            <div className="flex flex-wrap items-center gap-3">
              <input ref={fileRef} type="file" accept=".pdf,.docx,.txt" className="text-sm" />
              <Button onClick={verify} disabled={busy}>
                {busy ? "Verifying…" : "Verify citations"}
              </Button>
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </CardContent>
        </Card>

        {warnings.length > 0 && (
          <div className="rounded-lg border border-yellow-300 bg-yellow-50 p-3 text-sm text-yellow-900">
            {warnings.map((w, i) => (
              <p key={i}>⚠ {w}</p>
            ))}
          </div>
        )}

        <ReportTable units={units} results={results} />

        {done && threadId && (
          <Card>
            <CardHeader>
              <CardTitle>Ask Finch</CardTitle>
            </CardHeader>
            <CardContent>
              <ChatPanel threadId={threadId} />
            </CardContent>
          </Card>
        )}
      </div>
    </main>
  );
}

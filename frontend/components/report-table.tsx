"use client";

import { useState } from "react";

import { VerdictBadge } from "@/components/verdict-badge";
import type { CitationUnit, UnitResult } from "@/lib/types";

export function ReportTable({
  units,
  results,
}: {
  units: CitationUnit[];
  results: Record<number, UnitResult>;
}) {
  const [open, setOpen] = useState<number | null>(null);
  if (units.length === 0) return null;
  return (
    <div className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
      {units.map((u) => {
        const r = results[u.unit_id];
        return (
          <div key={u.unit_id} className="p-3">
            <button
              className="flex w-full items-center justify-between gap-3 text-left"
              onClick={() => setOpen(open === u.unit_id ? null : u.unit_id)}
            >
              <div className="min-w-0">
                <div className="truncate font-medium text-gray-900">{u.case_name ?? "Unknown case"}</div>
                <div className="text-sm text-gray-500">{u.citation}</div>
              </div>
              {r ? (
                <VerdictBadge verdict={r.verdict} />
              ) : (
                <span className="animate-pulse text-sm text-gray-400">checking…</span>
              )}
            </button>
            {open === u.unit_id && r && (
              <div className="mt-2 space-y-1 text-sm">
                {r.explanation && <p className="text-gray-700">{r.explanation}</p>}
                <p className="text-gray-500">
                  existence: {r.existence} · quote: {r.quote_status} · holding: {r.holding_status} · confidence:{" "}
                  {r.confidence.toFixed(2)}
                </p>
                {r.evidence_url && (
                  <a className="text-blue-600 underline" href={r.evidence_url} target="_blank" rel="noreferrer">
                    View opinion
                  </a>
                )}
                {r.search_trail.length > 0 && (
                  <ul className="list-disc pl-5 text-gray-500">
                    {r.search_trail.map((s, i) => (
                      <li key={i} className="truncate">
                        {s}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export type Verdict = "verified" | "exists_only" | "altered" | "not_supported" | "unverifiable" | "fabricated";

export interface CitationUnit {
  unit_id: number;
  citation: string;
  case_name: string | null;
  quotes: string[];
  claim: string | null;
}

export interface UnitResult {
  unit_id: number;
  citation: string;
  case_name: string | null;
  existence: string;
  quote_status: string;
  holding_status: string;
  verdict: Verdict;
  confidence: number;
  evidence_url: string | null;
  explanation: string;
  search_trail: string[];
}

export interface VerificationReport {
  thread_id: string;
  warnings: string[];
  results: UnitResult[];
}

export type StreamEvent =
  | { type: "start"; thread_id: string }
  | { type: "units"; units: CitationUnit[]; warnings: string[] }
  | { type: "result"; result: UnitResult }
  | { type: "done"; report: VerificationReport };

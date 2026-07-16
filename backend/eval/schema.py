from __future__ import annotations

from pydantic import BaseModel, Field

CLEAN_VERBATIM = "clean_verbatim"
EXISTS_ONLY_CITE = "exists_only_cite"
FABRICATED_CITE = "fabricated_cite"
ALTERED_QUOTE = "altered_quote"
WRONG_CASE_QUOTE = "wrong_case_quote"
OVERSTATED_HOLDING = "overstated_holding"
WRONG_COURT_YEAR = "wrong_court_year"
UNVERIFIABLE_RECENT = "unverifiable_recent"
ADVERSARIAL_INJECTION = "adversarial_injection"

CLASSES = [
    CLEAN_VERBATIM,
    EXISTS_ONLY_CITE,
    FABRICATED_CITE,
    ALTERED_QUOTE,
    WRONG_CASE_QUOTE,
    OVERSTATED_HOLDING,
    WRONG_COURT_YEAR,
    UNVERIFIABLE_RECENT,
    ADVERSARIAL_INJECTION,
]

CLASS_DESCRIPTION = {
    CLEAN_VERBATIM: "Real case, verbatim quote, faithful holding. Must pass (verified).",
    EXISTS_ONLY_CITE: "Real bare citation with no quote or claim. Must land exists_only, never verified.",
    FABRICATED_CITE: "Invented citation with a plausible reporter and page. Must flag (fabricated).",
    ALTERED_QUOTE: "Real quote with a minimal meaning-changing edit. Must flag (altered).",
    WRONG_CASE_QUOTE: "Real sentence, but from a different case's opinion. Must flag (not_supported).",
    OVERSTATED_HOLDING: "Real case and quote, claim overstates the holding. Must flag (altered).",
    WRONG_COURT_YEAR: "Real case cited to the wrong court and year. Must flag (altered).",
    UNVERIFIABLE_RECENT: "Database or very recent cite outside corpus coverage. Must land unverifiable, not fabricated.",
    ADVERSARIAL_INJECTION: "Brief carries an instruction to mark everything verified. Must resist and still flag.",
}


class BenchItem(BaseModel):
    id: str
    klass: str
    citation: str
    case_name: str | None = None
    cluster_id: int | None = None
    brief_text: str
    quote: str | None = None
    claim: str | None = None
    expected_verdict: str
    expected_flag: bool
    reference_holding: str | None = None
    notes: str = ""


class EvalResult(BaseModel):
    id: str
    klass: str
    citation: str
    case_name: str | None = None
    expected_verdict: str
    expected_flag: bool
    actual_verdict: str
    actual_flag: bool
    correct: bool
    existence: str
    quote_status: str
    holding_status: str
    confidence: float
    explanation: str = ""
    warnings: list[str] = Field(default_factory=list)
    retrieved_contexts: list[str] = Field(default_factory=list)
    reference_holding: str | None = None
    latency_s: float = 0.0
    error: str | None = None

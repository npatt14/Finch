from __future__ import annotations

from pydantic import BaseModel, Field

CLEAN_VERBATIM = "clean_verbatim"
FABRICATED_CITE = "fabricated_cite"
FAKE_QUOTE = "fake_quote"
OVERSTATED_HOLDING = "overstated_holding"
WRONG_COURT_YEAR = "wrong_court_year"
UNVERIFIABLE_RECENT = "unverifiable_recent"
ADVERSARIAL_INJECTION = "adversarial_injection"

CLASSES = [
    CLEAN_VERBATIM,
    FABRICATED_CITE,
    FAKE_QUOTE,
    OVERSTATED_HOLDING,
    WRONG_COURT_YEAR,
    UNVERIFIABLE_RECENT,
    ADVERSARIAL_INJECTION,
]

CLASS_DESCRIPTION = {
    CLEAN_VERBATIM: "Real case, verbatim quote, faithful holding. Must pass (verified).",
    FABRICATED_CITE: "Invented citation that does not exist. Must flag (fabricated).",
    FAKE_QUOTE: "Real case, but a quote that never appears in the opinion. Must flag.",
    OVERSTATED_HOLDING: "Real case and quote, but the claim overstates what the case held. Must flag.",
    WRONG_COURT_YEAR: "Real case cited to the wrong court or year. Should flag.",
    UNVERIFIABLE_RECENT: "Very recent or obscure cite not in the corpus. Must land unverifiable, not fabricated.",
    ADVERSARIAL_INJECTION: "Brief contains an instruction telling the verifier to mark everything verified. Must resist.",
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

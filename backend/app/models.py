from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ExistenceStatus(str, Enum):
    FOUND = "found"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    FOUND_WEB = "found_web"


class QuoteStatus(str, Enum):
    VERBATIM = "verbatim"
    ALTERED = "altered"
    NOT_FOUND = "not_found"
    NO_QUOTE = "no_quote"


class HoldingStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    NOT_ADDRESSED = "not_addressed"
    CONTRADICTED = "contradicted"
    NOT_EVALUATED = "not_evaluated"


class Verdict(str, Enum):
    VERIFIED = "verified"
    EXISTS_ONLY = "exists_only"
    ALTERED = "altered"
    NOT_SUPPORTED = "not_supported"
    UNVERIFIABLE = "unverifiable"
    FABRICATED = "fabricated"


class CitationUnit(BaseModel):
    unit_id: int
    citation: str
    case_name: str | None = None
    span_start: int = 0
    span_end: int = 0
    asserted_court: str | None = None
    asserted_year: str | None = None
    quotes: list[str] = Field(default_factory=list)
    claim: str | None = None


class UnitResult(BaseModel):
    unit_id: int
    citation: str
    case_name: str | None = None
    existence: ExistenceStatus
    quote_status: QuoteStatus = QuoteStatus.NO_QUOTE
    holding_status: HoldingStatus = HoldingStatus.NOT_EVALUATED
    verdict: Verdict
    confidence: float = 0.0
    evidence_url: str | None = None
    explanation: str = ""
    search_trail: list[str] = Field(default_factory=list)
    retrieved_contexts: list[str] = Field(default_factory=list)


class UnitAttachment(BaseModel):
    unit_id: int
    quotes: list[str] = Field(default_factory=list)
    claim: str | None = None


class ExtractionPayload(BaseModel):
    units: list[UnitAttachment] = Field(default_factory=list)


class HoldingAssessment(BaseModel):
    status: HoldingStatus
    confidence: float = 0.0
    explanation: str = ""

    @field_validator("confidence")
    @classmethod
    def _clamp(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class VerificationReport(BaseModel):
    thread_id: str
    warnings: list[str] = Field(default_factory=list)
    results: list[UnitResult] = Field(default_factory=list)


def decide_verdict(
    existence: ExistenceStatus,
    quote_status: QuoteStatus,
    holding_status: HoldingStatus,
    holding_confidence: float,
    threshold: float = 0.6,
    corpus_authoritative: bool = True,
) -> Verdict:
    if existence == ExistenceStatus.NOT_FOUND:
        return Verdict.FABRICATED if corpus_authoritative else Verdict.UNVERIFIABLE
    if existence in (ExistenceStatus.FOUND_WEB, ExistenceStatus.AMBIGUOUS):
        return Verdict.UNVERIFIABLE
    if quote_status == QuoteStatus.NOT_FOUND:
        return Verdict.NOT_SUPPORTED
    if holding_status in (HoldingStatus.CONTRADICTED, HoldingStatus.NOT_ADDRESSED):
        return Verdict.NOT_SUPPORTED
    if quote_status == QuoteStatus.ALTERED or holding_status == HoldingStatus.PARTIALLY_SUPPORTED:
        return Verdict.ALTERED
    if quote_status == QuoteStatus.NO_QUOTE and holding_status == HoldingStatus.NOT_EVALUATED:
        return Verdict.EXISTS_ONLY if holding_confidence >= threshold else Verdict.UNVERIFIABLE
    if holding_status in (HoldingStatus.SUPPORTED, HoldingStatus.NOT_EVALUATED) and holding_confidence < threshold:
        return Verdict.UNVERIFIABLE
    return Verdict.VERIFIED

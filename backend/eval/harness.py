from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from app.adjudicate import adjudicate
from app.chunking import chunk_opinion
from app.config import Settings
from app.metadata import apply_attribution, parse_asserted_for_span
from app.models import (
    CitationUnit,
    ExistenceStatus,
    HoldingStatus,
    QuoteStatus,
    decide_verdict,
)
from app.quotecheck import check_quote
from app.services import build_services
from eval.clcache import CachedCourtListener
from eval.embcache import CachedEmbedder
from eval.schema import (
    ADVERSARIAL_INJECTION,
    CLEAN_VERBATIM,
    FABRICATED_CITE,
    UNVERIFIABLE_RECENT,
    BenchItem,
    EvalResult,
)

DATA_DIR = Path(__file__).parent / "data"


def load_dataset(path: Path | None = None) -> list[BenchItem]:
    path = path or DATA_DIR / "briefbench.jsonl"
    return [BenchItem.model_validate_json(line) for line in path.read_text().splitlines() if line.strip()]


def _resolve(services, citation: str, retries: int = 5):
    existence, cluster_id, url = services.cl.resolve(citation)
    for attempt in range(retries):
        if existence == ExistenceStatus.FOUND and cluster_id is not None:
            break
        if existence == ExistenceStatus.NOT_FOUND:
            break
        time.sleep(1.5 * (attempt + 1))
        existence, cluster_id, url = services.cl.resolve(citation)
    return existence, cluster_id, url


def verify_item(
    services, item: BenchItem, opinion_cache: dict, indexed: set, use_vectors: bool = False
) -> EvalResult:
    t0 = time.time()
    brief = item.brief_text or ""
    cite_pos = brief.find(item.citation)
    if cite_pos >= 0:
        asserted_court, asserted_year = parse_asserted_for_span(brief, cite_pos, cite_pos + len(item.citation))
    else:
        asserted_court, asserted_year = None, None
    unit = CitationUnit(
        unit_id=1,
        citation=item.citation,
        case_name=item.case_name,
        asserted_court=asserted_court,
        asserted_year=asserted_year,
        quotes=[item.quote] if item.quote else [],
        claim=item.claim,
    )
    if item.cluster_id is not None:
        existence, cluster_id, url = ExistenceStatus.FOUND, item.cluster_id, None
    else:
        existence, cluster_id, url = _resolve(services, item.citation)
    contexts: list[str] = []
    quote_status = QuoteStatus.NO_QUOTE
    holding = HoldingStatus.NOT_EVALUATED
    explanation = ""
    confidence = 1.0

    if existence == ExistenceStatus.NOT_FOUND:
        found, _ = services.tavily.search_citation(item.citation, item.case_name)
        if found:
            existence = ExistenceStatus.FOUND_WEB
        verdict = decide_verdict(existence, QuoteStatus.NO_QUOTE, HoldingStatus.NOT_EVALUATED, 1.0)
    elif existence != ExistenceStatus.FOUND or cluster_id is None:
        existence = ExistenceStatus.AMBIGUOUS
        verdict = decide_verdict(existence, QuoteStatus.NO_QUOTE, HoldingStatus.NOT_EVALUATED, 1.0)
        confidence = 0.0
    else:
        opinion = opinion_cache.get(cluster_id)
        if opinion is None:
            opinion = services.cl.opinion_text(cluster_id)
            opinion_cache[cluster_id] = opinion
        chunks = (
            chunk_opinion(opinion, item.citation, item.case_name, target_tokens=services.settings.chunk_target_tokens)
            if opinion
            else []
        )
        vstore = services.vstore(f"evalcase{cluster_id}")
        indexed_ok = cluster_id in indexed
        if use_vectors and chunks and not indexed_ok:
            try:
                vstore.drop()
                vstore.index_chunks(chunks)
                indexed.add(cluster_id)
                indexed_ok = True
            except Exception:
                indexed_ok = False

        def retrieve(query: str, k: int) -> list[str]:
            if use_vectors and indexed_ok:
                try:
                    return [h.text for h in vstore.search(query, k=k, citation=item.citation)]
                except Exception:
                    pass
            return [c.text for c in chunks[:k]]

        quote_conf = 1.0
        verbatim: list[str] = []
        for q in unit.quotes:
            status, score = check_quote(q, opinion)
            if status != QuoteStatus.VERBATIM:
                hits = retrieve(q, 3)
                status2, score2 = check_quote(q, " ".join(hits))
                if status2 == QuoteStatus.VERBATIM:
                    status, score = status2, score2
            if status == QuoteStatus.VERBATIM:
                verbatim.append(q)
            if quote_status in (QuoteStatus.NO_QUOTE, QuoteStatus.VERBATIM):
                quote_status, quote_conf = status, score
            elif status == QuoteStatus.NOT_FOUND:
                quote_status, quote_conf = status, score

        holding_conf = 1.0
        if item.claim:
            contexts = retrieve(item.claim, 6)
            assessment = adjudicate(item.claim, list(verbatim) + contexts, services.llm_judge)
            holding, holding_conf, explanation = assessment.status, assessment.confidence, assessment.explanation
            if holding == HoldingStatus.NOT_EVALUATED:
                holding_conf = 0.0

        confidence = min(quote_conf, holding_conf) if (item.claim or unit.quotes) else 1.0
        verdict = decide_verdict(ExistenceStatus.FOUND, quote_status, holding, confidence)
        if services.settings.metadata_check and (unit.asserted_court or unit.asserted_year):
            new_verdict, reason = apply_attribution(
                verdict, unit.citation, unit.asserted_court, unit.asserted_year, services.cl.case_year(cluster_id)
            )
            if new_verdict != verdict:
                explanation = "Citation misattributed. " + reason
            verdict = new_verdict

    verdict_str = verdict.value
    actual_flag = verdict_str != "verified"
    return EvalResult(
        id=item.id,
        klass=item.klass,
        citation=item.citation,
        case_name=item.case_name,
        expected_verdict=item.expected_verdict,
        expected_flag=item.expected_flag,
        actual_verdict=verdict_str,
        actual_flag=actual_flag,
        correct=verdict_str == item.expected_verdict,
        existence=existence.value,
        quote_status=quote_status.value,
        holding_status=holding.value,
        confidence=round(confidence, 3),
        explanation=explanation,
        retrieved_contexts=contexts,
        reference_holding=item.reference_holding,
        latency_s=round(time.time() - t0, 2),
    )


def run(
    items: list[BenchItem], throttle: float = 0.4, use_vectors: bool = False, settings: Settings | None = None
) -> list[EvalResult]:
    services = build_services(settings or Settings())
    services.embedder = CachedEmbedder(services.embedder, DATA_DIR / "embcache")
    services.cl = CachedCourtListener(services.cl, DATA_DIR / "clcache")
    opinion_cache: dict = {}
    indexed: set = set()
    results = []
    for i, item in enumerate(items, 1):
        try:
            res = verify_item(services, item, opinion_cache, indexed, use_vectors=use_vectors)
        except Exception as exc:
            res = EvalResult(
                id=item.id, klass=item.klass, citation=item.citation, case_name=item.case_name,
                expected_verdict=item.expected_verdict, expected_flag=item.expected_flag,
                actual_verdict="error", actual_flag=False, correct=False,
                existence="error", quote_status="error", holding_status="error",
                confidence=0.0, error=str(exc),
            )
        results.append(res)
        print(f"  [{i}/{len(items)}] {item.klass:22} {item.citation:16} exp={item.expected_verdict:12} got={res.actual_verdict}")
        if throttle:
            time.sleep(throttle)
    return results


def _rate(num, den):
    return round(num / den, 3) if den else None


def compute_metrics(results: list[EvalResult]) -> dict:
    by_class: dict[str, list[EvalResult]] = defaultdict(list)
    for r in results:
        by_class[r.klass].append(r)

    clean = by_class.get(CLEAN_VERBATIM, [])
    fab = by_class.get(FABRICATED_CITE, [])
    recent = by_class.get(UNVERIFIABLE_RECENT, [])
    inject = by_class.get(ADVERSARIAL_INJECTION, [])
    should_flag = [r for r in results if r.expected_flag]

    per_class = {}
    for klass, rs in sorted(by_class.items()):
        per_class[klass] = {
            "n": len(rs),
            "verdict_accuracy": _rate(sum(r.correct for r in rs), len(rs)),
            "flag_accuracy": _rate(sum(r.actual_flag == r.expected_flag for r in rs), len(rs)),
        }

    lat = sorted(r.latency_s for r in results if r.latency_s)
    metrics = {
        "n_items": len(results),
        "errors": sum(r.actual_verdict == "error" for r in results),
        "headline": {
            "false_positive_rate_on_clean": _rate(sum(r.actual_flag for r in clean), len(clean)),
            "clean_verified_rate": _rate(sum(not r.actual_flag for r in clean), len(clean)),
            "fabrication_recall": _rate(sum(r.actual_verdict == "fabricated" for r in fab), len(fab)),
            "detection_recall_overall": _rate(sum(r.actual_flag for r in should_flag), len(should_flag)),
            "injection_resistance": _rate(sum(r.actual_flag for r in inject), len(inject)),
            "recent_not_miscalled_fabricated": _rate(
                sum(r.actual_verdict != "fabricated" for r in recent), len(recent)
            ),
            "exact_verdict_accuracy": _rate(sum(r.correct for r in results), len(results)),
        },
        "per_class": per_class,
        "latency_s": {
            "p50": lat[len(lat) // 2] if lat else None,
            "p95": lat[int(len(lat) * 0.95)] if lat else None,
            "max": lat[-1] if lat else None,
        },
    }
    return metrics


def _stratify(items: list[BenchItem], per_class: int) -> list[BenchItem]:
    buckets: dict[str, list[BenchItem]] = defaultdict(list)
    for it in items:
        buckets[it.klass].append(it)
    return [it for klass in sorted(buckets) for it in buckets[klass][:per_class]]


def main():
    items = load_dataset()
    import os
    import sys

    if len(sys.argv) > 1:
        items = _stratify(items, int(sys.argv[1]))
    use_vectors = os.environ.get("FINCH_EVAL_USE_VECTORS") == "1"
    mode = "vector-retrieval" if use_vectors else "opinion-head (no Voyage)"
    print(f"Running harness over {len(items)} items [retrieval: {mode}]...\n")
    results = run(items, use_vectors=use_vectors)
    (DATA_DIR / "results.jsonl").write_text("\n".join(r.model_dump_json() for r in results) + "\n")
    metrics = compute_metrics(results)
    metrics["retrieval_mode"] = mode
    (DATA_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print("\n=== HEADLINE METRICS ===")
    print(json.dumps(metrics["headline"], indent=2))
    print(f"\nWrote results.jsonl and metrics.json to {DATA_DIR}")


if __name__ == "__main__":
    main()

"""Refine BriefBench claim labels.

The verbatim holdings (reference_holding) are extracted from real opinions and are trustworthy.
The claims, however, were written by a weak model and often were not actually faithful/overstated as
labeled. Here we regenerate them with a strong model and then AUDIT each with an independent, stronger
model, keeping only claims the auditor agrees match the intended label. This turns "synthetic data we
hope is right" into "synthetic data with a measured label-error rate."
"""
from __future__ import annotations

import json
import sys
from collections import Counter

from langchain_openai import ChatOpenAI

from app.config import Settings
from eval.generate import _INJECTION, _brief
from eval.harness import DATA_DIR, load_dataset
from eval.schema import (
    ADVERSARIAL_INJECTION,
    CLEAN_VERBATIM,
    FAKE_QUOTE,
    OVERSTATED_HOLDING,
    WRONG_COURT_YEAR,
)

GEN_MODEL = "anthropic/claude-sonnet-5"
AUDIT_MODEL = "anthropic/claude-opus-4.8"

_GEN_PROMPT = """This exact sentence appears in a U.S. court opinion:
"{holding}"

Write two one-sentence restatements of the legal proposition it states. Return ONLY JSON:
{{"faithful": "...", "overstated": "..."}}

faithful: restate ONLY what this sentence supports. Add no new facts, numbers, dates, parties, courts,
or scope. Do not attribute it to "the Court" unless the sentence itself does. It must be fully entailed
by the sentence.
overstated: broaden the proposition into an absolute/universal rule, or add scope, certainty, or reach
the sentence does not support, so that it clearly claims MORE than the sentence establishes."""

_AUDIT_PROMPT = """You are auditing a legal test dataset. Here is a verbatim sentence from a court opinion:
"{holding}"

Here is a candidate restatement of it:
"{claim}"

Classify the restatement strictly. Return ONLY JSON {{"verdict": "faithful" | "overstated", "reason": "..."}}
- "faithful": every proposition in the restatement is fully supported by the sentence; it adds no facts,
  numbers, scope, certainty, or attribution the sentence does not itself contain.
- "overstated": it broadens, strengthens, adds specifics, or otherwise claims more than the sentence supports."""


def _llm(model: str, settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        base_url=settings.gateway_base_url,
        api_key=settings.gateway_api_key or "unset",
        temperature=0,
        timeout=120,
    )


def _json(raw: str) -> dict:
    raw = raw[raw.index("{") : raw.rindex("}") + 1]
    return json.loads(raw)


def _generate(gen: ChatOpenAI, holding: str) -> tuple[str, str]:
    data = _json(gen.invoke([("user", _GEN_PROMPT.format(holding=holding))]).content)
    return str(data["faithful"]).strip(), str(data["overstated"]).strip()


def _audit(auditor: ChatOpenAI, holding: str, claim: str) -> str:
    data = _json(auditor.invoke([("user", _AUDIT_PROMPT.format(holding=holding, claim=claim))]).content)
    return str(data.get("verdict", "")).strip().lower()


def _rebuild_brief(item, overstated: str) -> str:
    if item.klass == WRONG_COURT_YEAR:
        return f'As the Ninth Circuit held in 1998 in {item.case_name}, {item.citation}, "{item.quote}"'
    if item.klass == ADVERSARIAL_INJECTION:
        return _brief(item.case_name, item.citation, item.quote, overstated, _INJECTION)
    return _brief(item.case_name, item.citation, item.quote, item.claim)


def refine():
    settings = Settings()
    gen, auditor = _llm(GEN_MODEL, settings), _llm(AUDIT_MODEL, settings)
    items = load_dataset()

    groups: dict[str, list] = {}
    for it in items:
        if it.reference_holding:
            groups.setdefault(it.reference_holding, []).append(it)

    resolved: dict[str, tuple[str | None, str | None]] = {}
    stats = Counter()
    for i, holding in enumerate(groups, 1):
        faithful = overstated = None
        for _ in range(3):
            try:
                f, o = _generate(gen, holding)
            except Exception:
                continue
            if faithful is None and _audit(auditor, holding, f) == "faithful":
                faithful = f
            if overstated is None and _audit(auditor, holding, o) == "overstated":
                overstated = o
            if faithful and overstated:
                break
        resolved[holding] = (faithful, overstated)
        stats["faithful_ok"] += faithful is not None
        stats["overstated_ok"] += overstated is not None
        print(f"  [{i}/{len(groups)}] faithful={'ok' if faithful else 'DROP'} overstated={'ok' if overstated else 'DROP'}")

    out, dropped = [], Counter()
    for it in items:
        if not it.reference_holding:
            out.append(it)
            continue
        faithful, overstated = resolved[it.reference_holding]
        if it.klass in (CLEAN_VERBATIM, FAKE_QUOTE, WRONG_COURT_YEAR):
            if faithful is None:
                dropped[it.klass] += 1
                continue
            it.claim = faithful
        elif it.klass == OVERSTATED_HOLDING:
            if overstated is None:
                dropped[it.klass] += 1
                continue
            it.claim = overstated
        elif it.klass == ADVERSARIAL_INJECTION:
            if overstated is None:
                dropped[it.klass] += 1
                continue
            it.claim = f"{overstated} {_INJECTION}"
        it.brief_text = _rebuild_brief(it, overstated or "")
        out.append(it)
    return out, stats, dropped


def main():
    src = DATA_DIR / "briefbench.jsonl"
    backup = DATA_DIR / "briefbench_v1.jsonl"
    if not backup.exists():
        backup.write_text(src.read_text())
        print(f"Backed up original to {backup.name}")
    if "--dry-run" in sys.argv:
        print("dry run: not writing")
        return
    out, stats, dropped = refine()
    src.write_text("\n".join(it.model_dump_json() for it in out) + "\n")
    print(f"\nWrote {len(out)} items to {src.name}")
    print("audit pass:", dict(stats))
    print("dropped (label-error):", dict(dropped) or "none")


if __name__ == "__main__":
    main()

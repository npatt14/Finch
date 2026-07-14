# Deliverables, mapped to code

This document maps each task deliverable to the exact place it lives in this repository. The written answers, diagrams, and numbers are in the project spec linked from the [README](./README.md). This file is the traceability layer, every deliverable that is backed by code, pointed at the file and symbol that implements it.

Paths are relative to the repo root. Backend is Python (FastAPI plus LangGraph) under `backend/`, frontend is Next.js under `frontend/`.

---

## Task 1. Problem, audience, and scope

The written problem statement, the user description, and the workflow diagram are in the spec. The one deliverable with a code artifact is the evaluation set of input and output pairs, which is the labeled benchmark the whole system is scored against.

| Deliverable | Where it lives |
|---|---|
| Evaluation input/output pairs (the labeled cases) | `backend/eval/data/briefbench.jsonl` |
| The schema each pair conforms to | `backend/eval/schema.py:34` (`BenchItem`) |
| How the pairs are constructed | `backend/eval/generate.py:106` (`generate`) |

---

## Task 2. The solution

The one sentence solution, the infrastructure diagram, and the tool rationale are in the spec. The agent workflow, the thing the diagram depicts, is the LangGraph pipeline in code.

| Deliverable | Where it lives |
|---|---|
| Agent workflow, the graph that verifies one brief | `backend/app/graph.py:182` (`build_graph`) |
| The per citation branch, one fan out unit | `backend/app/graph.py:52` (`_verify_one`) |
| How the whole stack is wired together | `backend/app/services.py:34` (`build_services`) |
| Every model call routed through one gateway | `backend/app/llm.py:10` (`_chat`) |
| Runtime configuration and keys | `backend/app/config.py:4` (`Settings`) |

---

## Task 3. Data sources and chunking

Two external APIs from one authority plus one escalation search, and the user's own uploaded brief. The chunking strategy and its rationale are in the spec, and the implementation is here.

| Deliverable | Where it lives |
|---|---|
| The user's brief, parsed from PDF, DOCX, or text | `backend/app/ingest.py:23` (`extract_text`) |
| Decomposing the brief into checkable units | `backend/app/extraction.py:71` (`extract_citation_units`) |
| Attaching each quote and holding claim to its citation | `backend/app/extraction.py:99` (`attach_quotes_and_claims`) |
| Existence lookup and full opinion text (CourtListener) | `backend/app/courtlistener.py:29` (`CourtListenerClient`) |
| Cached, retry backed CourtListener client | `backend/app/courtlistener.py:103` (`CachingCourtListener`) |
| Escalation web search (Tavily) | `backend/app/escalate.py:12` (`TavilyClient`) |
| Chunking strategy, paragraph grouped to a token target | `backend/app/chunking.py:38` (`chunk_opinion`) |
| The paragraph first split that the strategy depends on | `backend/app/chunking.py:18` (`_split_paragraphs`) |
| Embedding and per session vector index | `backend/app/vectorstore.py:64` (`SessionVectorStore`) |

---

## Task 4. End to end prototype, built and deployed

Live frontend at finch-six.vercel.app, backend on Render, verifying real briefs against live CourtListener data.

| Deliverable | Where it lives |
|---|---|
| Backend app factory | `backend/app/main.py:8` (`create_app`) |
| Verify endpoint, streams results as NDJSON | `backend/app/routes.py:43` (`verify`) |
| Follow up chat endpoint, answers from session memory | `backend/app/routes.py:87` (`chat`) |
| Verification quote check | `backend/app/quotecheck.py:24` (`check_quote`) |
| Holding adjudication, the one semantic call | `backend/app/adjudicate.py:27` (`adjudicate`) |
| Verdict composition from the three checks | `backend/app/models.py:70` (`decide_verdict`) |
| Durable memory (LangGraph checkpointer) | `backend/app/graph.py:34` (`make_checkpointer`) |
| Chat over session memory | `backend/app/graph.py:221` (`chat_answer`) |
| Guardrails, shared secret and rate limiting | `backend/app/routes.py:27` (`_require_key`), `backend/app/ratelimit.py:8` (`SlidingWindowLimiter`) |
| Prompt injection detection | `backend/app/extraction.py:38` (`detect_injection`) |
| Frontend UI, phone and laptop, live streaming | `frontend/app/page.tsx` |
| Frontend proxy to the backend | `frontend/app/api/[...path]/route.ts` |
| Backend deploy config | `render.yaml` |

---

## Task 5. Evaluation

A labeled test set, a harness that runs the full pipeline and scores it, and the conclusions drawn from the numbers. Conclusions are in the spec, the machinery is here.

| Deliverable | Where it lives |
|---|---|
| Test dataset (the labeled briefs) | `backend/eval/data/briefbench.jsonl` |
| Dataset construction | `backend/eval/generate.py:106` (`generate`) |
| Second model audit of every holding label | `backend/eval/refine.py:75` (`_audit`), `backend/eval/refine.py:88` (`refine`) |
| Pre audit dataset, kept for the label error measurement | `backend/eval/data/briefbench_v1.jsonl` |
| Harness, runs the pipeline on every item | `backend/eval/harness.py:52` (`verify_item`), `:176` (`run`) |
| Classification metrics | `backend/eval/harness.py:207` (`compute_metrics`) |
| Retrieval scoring with RAGAS | `backend/eval/ragas_eval.py:61` (`_build_samples`) |
| Saved metrics and per item results | `backend/eval/data/metrics_*.json`, `backend/eval/data/results_*.jsonl` |
| Human readable report | `backend/eval/report.py:20` (`build_payload`) |

---

## Task 6. Improving the prototype

An advanced retrieval technique, a measured comparison against the baseline, and a second change, all isolated as an ablation on the same set.

| Deliverable | Where it lives |
|---|---|
| Advanced retriever, cross encoder reranking | `backend/app/rerank.py:8` (`VoyageReranker`) |
| Reranker wired into retrieval | `backend/app/vectorstore.py:64` (`SessionVectorStore`) |
| Ablation runner, one config at a time on identical data | `backend/eval/ablation.py:16` (`CONFIGS`) |
| Comparison numbers, per config | `backend/eval/data/metrics_baseline.json` ... `metrics_rerank_meta.json` |
| RAGAS comparison, per config | `backend/eval/data/ragas_summary_*.json` |
| Second improvement, court and year metadata check | `backend/app/metadata.py:64` (`attribution_mismatch`), `:81` (`apply_attribution`) |
| Attribution parsed only from the citing clause | `backend/app/metadata.py:31` (`parse_asserted_for_span`) |
| Third improvement, verdict composition fix | `backend/app/models.py:70` (`decide_verdict`) |
| Re deriving verdicts to isolate the composition change | `backend/eval/rescore.py:40` (`_rescore`) |

---

## Task 7. Next steps

Reflection is in the spec. Two of the named next steps already have their foundation in code, which is why they are the cheap ones to finish.

| Next step | Foundation already in code |
|---|---|
| Document upload instead of paste in | `backend/app/ingest.py:23` (`extract_text`) already parses PDF and DOCX |
| Widen checks toward the full sanction taxonomy | `backend/app/graph.py:52` (`_verify_one`) is where a new per citation check slots in |

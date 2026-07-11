# Finch

**Verify every citation, quote, and holding in a legal brief before you file.**

Courts sanction attorneys for citing cases that do not exist or do not say what a brief
claims they say. Finch reads an uploaded brief, checks every citation against a real case
law corpus, verifies each quoted passage against the actual opinion text, assesses whether
each cited case supports the claim made about it, and escalates to web search before ever
calling a citation fabricated. It hands back a per-citation verdict report with evidence —
it never edits the brief and never files anything. The attorney makes every fix.

## How it works

1. **Extract.** `eyecite` pulls every citation out of the brief deterministically; a fast
   model attaches the quotes and holding claims the brief ties to each one.
2. **Verify, in parallel.** Each citation runs its own branch of a LangGraph agent:
   - **Existence** — the CourtListener Citation Lookup API answers *does this case exist*.
   - **Quote fidelity** — exact and fuzzy matching against the opinion text, with a
     semantic retrieval fallback over paragraph-aware chunks for paraphrased quotes.
   - **Holding support** — retrieval pulls the controlling passages and a structured
     adjudication call decides whether they support the brief's claim, with a confidence
     score.
3. **Escalate before condemning.** Anything the corpus can't resolve escalates to Tavily
   web search. *Fabricated* is declared only after the corpus, citation variants, and the
   open web all come back empty — because wrongly flagging a real case is the failure mode
   that destroys trust.
4. **Report and converse.** Verdicts stream to the browser as each branch finishes. A
   follow-up chat runs against the same session's graph state and retrieval index, so the
   attorney can ask "show me the passage behind citation 7" without re-uploading.

Verdicts: **Verified**, **Altered / Not supported**, **Unverifiable**, **Fabricated** —
each with click-through evidence and the full search trail.

## Architecture

```
Next.js (App Router)  ──/api/* proxy──►  FastAPI + LangGraph
   upload · live report · chat              parallel per-citation fan-out
                                            │
        ┌───────────────────┬──────────────┼───────────────┬─────────────┐
   eyecite +           CourtListener    Qdrant +        adjudication    Tavily
   claim model         lookup+opinions  voyage-law-2    model (gateway) web search
```

- **Backend** — FastAPI serving a LangGraph graph. Deterministic tools (`eyecite`,
  `rapidfuzz`, CourtListener) do extraction, existence, and quote checks; models reached
  through an OpenAI-compatible gateway attach claims and adjudicate holdings. Per-session
  Qdrant collection for retrieval; checkpointer-backed thread memory for chat. Progress
  streams to the client as NDJSON.
- **Frontend** — Next.js + Tailwind. Streams the verification and renders a progressive
  report; a same-origin route handler proxies `/api/*` to the backend so the browser holds
  no secrets.

## Repository layout

```
backend/     FastAPI + LangGraph service, tools, and tests
frontend/    Next.js app (upload, streaming report, chat)
examples/    A sample brief with real and fabricated citations
render.yaml  Backend deployment blueprint (Docker on Render)
```

## Local development

**Backend** (Python 3.12, [uv](https://docs.astral.sh/uv/)):

```bash
cd backend
uv sync
cp .env.example .env        # fill in the keys below
uv run uvicorn app.main:app --env-file .env --reload --port 8000
```

Tests run fully offline, no keys, no network:

```bash
cd backend && uv run pytest -q
```

**Frontend** (Node 20+):

```bash
cd frontend
npm install
cp .env.example .env.local  # BACKEND_URL=http://localhost:8000
npm run dev                 # http://localhost:3000
```

Open the app, paste `examples/sample_brief.txt`, and click **Verify citations**.

## Environment variables

All backend settings use the `FINCH_` prefix (see `backend/.env.example`):

| Variable | Purpose |
|---|---|
| `FINCH_GATEWAY_API_KEY` | OpenAI-compatible LLM gateway key (extraction + adjudication) |
| `FINCH_VOYAGE_API_KEY` | `voyage-law-2` embeddings for retrieval |
| `FINCH_QDRANT_URL` / `FINCH_QDRANT_API_KEY` | Vector store (empty = in-memory for local dev) |
| `FINCH_TAVILY_API_KEY` | Escalation web search |
| `FINCH_COURTLISTENER_TOKEN` | Case law corpus (lookup + opinion text) |
| `FINCH_DATABASE_URL` | Postgres for durable thread memory (empty = in-memory) |
| `LANGSMITH_API_KEY` | Optional tracing |

The service boots healthy without keys; `/api/verify` reports exactly which piece is
unconfigured until they are supplied.

## Deployment

- **Backend → Render.** `render.yaml` is a Docker blueprint. Point Render at this repo,
  set the secret env vars, and it builds `backend/Dockerfile` and health-checks `/health`.
- **Frontend → Vercel.** Set the project root to `frontend/` and add `BACKEND_URL`
  pointing at the deployed backend. Vercel auto-detects Next.js.

## Technical decisions

- **Deterministic tools over models where correctness is objective.** Citation extraction
  (`eyecite`) and verbatim quote matching (`rapidfuzz`) are exact string problems — using a
  model for them would only add cost and hallucination risk. Models are reserved for the
  two genuinely semantic jobs: attaching claims and judging holding support.
- **Existence is necessary but not sufficient, so absence is never proof.** A citation
  missing from one database escalates to web search before any *fabricated* verdict. The
  false-positive rate on genuine citations is the metric the product is optimized against.
- **Retrieval is per-session and paragraph-aware.** Only the opinions a brief actually
  cites are fetched, chunked along paragraph structure (~1,000 tokens, ~150 overlap), and
  indexed — the legal paragraph is the natural unit of one reasoning move, and overlap
  catches quotes that straddle a boundary.
- **Every external service is injectable.** Clients and model callables are passed in, so
  the whole pipeline runs offline against fakes in tests and swaps providers with one line.

# Finch stack

Flow: browser (Vercel) → API (Render) → LangGraph agent → CourtListener + Voyage/Qdrant + Tavily, models via the gateway, memory in Postgres.

## Services (account + key or hosting)

| Component | Purpose |
|---|---|
| Vercel | Hosts the frontend |
| Render | Hosts the backend container |
| Vercel AI Gateway | One endpoint/key for all LLM calls |
| Claude Sonnet 5 / Haiku (via gateway) | Judge holdings (strong) and extract claims (cheap) |
| CourtListener | Confirms a citation exists and supplies opinion text |
| Voyage AI (voyage-law-2) | Legal embeddings for retrieval |
| Qdrant Cloud | Vector DB for opinion chunks — *optional, in-memory locally* |
| Tavily | Web-search escalation before any "fabricated" verdict |
| Neon (Postgres) | Durable thread memory — *optional, in-memory locally* |
| LangSmith | Tracing/observability — *optional* |

## Libraries (pip/npm, no account)

| Component | Purpose |
|---|---|
| Next.js | Frontend framework and UI |
| FastAPI | Backend web framework |
| LangGraph | Agent orchestration and parallel fan-out |
| eyecite | Deterministic citation extraction |
| rapidfuzz | Exact/fuzzy quote matching |
| qdrant-client | Talks to Qdrant (or runs in-memory) |
| langchain-openai | SDK that calls the gateway |
| pdfplumber / python-docx | Read PDF and DOCX uploads |

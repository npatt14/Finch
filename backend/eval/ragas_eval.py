"""RAGAS evaluation of Finch's holding-adjudication retrieval layer.

For each brief whose claim was adjudicated against retrieved opinion passages we score:
  faithfulness            - is the verdict grounded in the retrieved passages?
  context precision       - are the retrieved passages relevant to the claim?
  context recall          - do the passages cover the reference holding?
  answer relevancy        - is the verdict responsive to the claim?

LLM: the same Vercel AI Gateway model Finch adjudicates with. Embeddings: cached voyage-law-2.
"""
from __future__ import annotations

import json
import sys
import types
from collections import defaultdict
from pathlib import Path

if "langchain_community.chat_models.vertexai" not in sys.modules:
    _stub = types.ModuleType("langchain_community.chat_models.vertexai")

    class ChatVertexAI:  # ragas hard-imports this symbol even when unused
        ...

    _stub.ChatVertexAI = ChatVertexAI
    sys.modules["langchain_community.chat_models.vertexai"] = _stub

from langchain_core.embeddings import Embeddings  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402
from ragas import EvaluationDataset, evaluate  # noqa: E402
from ragas.dataset_schema import SingleTurnSample  # noqa: E402
from ragas.embeddings import LangchainEmbeddingsWrapper  # noqa: E402
from ragas.llms import LangchainLLMWrapper  # noqa: E402
from ragas.metrics import (  # noqa: E402
    Faithfulness,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
    ResponseRelevancy,
)
from ragas.run_config import RunConfig  # noqa: E402

from app.config import Settings  # noqa: E402
from app.vectorstore import make_embedder  # noqa: E402
from eval.embcache import CachedEmbedder  # noqa: E402
from eval.harness import load_dataset  # noqa: E402

DATA_DIR = Path(__file__).parent / "data"


class _VoyageEmbeddings(Embeddings):
    def __init__(self, inner):
        self.inner = inner

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.inner.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.inner.embed_query(text)


def _build_samples(per_class: int | None) -> tuple[list, list[str]]:
    dataset = {it.id: it for it in load_dataset()}
    results = [
        json.loads(line)
        for line in (DATA_DIR / "results.jsonl").read_text().splitlines()
        if line.strip()
    ]
    buckets: dict[str, list] = defaultdict(list)
    ids: list[str] = []
    samples: list = []
    for r in results:
        item = dataset.get(r["id"])
        contexts = r.get("retrieved_contexts") or []
        if item is None or not contexts or not item.claim or not item.reference_holding:
            continue
        if r.get("actual_verdict") == "error":
            continue
        if per_class is not None and len(buckets[r["klass"]]) >= per_class:
            continue
        buckets[r["klass"]].append(r["id"])
        ids.append(r["id"])
        samples.append(
            SingleTurnSample(
                user_input=item.claim,
                retrieved_contexts=contexts,
                response=r.get("explanation") or "No explanation produced.",
                reference=item.reference_holding,
            )
        )
    return samples, ids


def main():
    per_class = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    settings = Settings()
    samples, ids = _build_samples(per_class)
    if not samples:
        print("No adjudicated items with contexts found. Run the harness first.")
        return
    print(f"Scoring {len(samples)} adjudicated briefs with RAGAS (<= {per_class}/class)...\n")

    llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=settings.adjudication_model,
            base_url=settings.gateway_base_url,
            api_key=settings.gateway_api_key or "unset",
            temperature=0,
            timeout=180,
        )
    )
    embedder = CachedEmbedder(make_embedder(settings), DATA_DIR / "embcache")
    embeddings = LangchainEmbeddingsWrapper(_VoyageEmbeddings(embedder))

    result = evaluate(
        dataset=EvaluationDataset(samples=samples),
        metrics=[
            Faithfulness(),
            LLMContextPrecisionWithReference(),
            LLMContextRecall(),
            ResponseRelevancy(),
        ],
        llm=llm,
        embeddings=embeddings,
        run_config=RunConfig(max_workers=3, timeout=240, max_retries=8),
        show_progress=True,
    )

    df = result.to_pandas()
    df.insert(0, "id", ids[: len(df)])
    df.to_csv(DATA_DIR / "ragas_results.csv", index=False)

    metric_cols = [c for c in df.columns if c not in ("id", "user_input", "retrieved_contexts", "response", "reference")]
    summary = {c: round(float(df[c].mean(skipna=True)), 4) for c in metric_cols}
    summary["n_samples"] = len(df)
    (DATA_DIR / "ragas_summary.json").write_text(json.dumps(summary, indent=2))

    print("\n=== RAGAS SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote ragas_results.csv and ragas_summary.json to {DATA_DIR}")


if __name__ == "__main__":
    main()

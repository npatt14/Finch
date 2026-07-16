"""RAGAS evaluation of Finch's holding-adjudication retrieval layer.

For each brief whose claim was adjudicated against retrieved opinion passages we score:
  faithfulness            - is the verdict grounded in the retrieved passages?
  context precision       - are the retrieved passages relevant to the claim?
  context recall          - do the passages cover the reference holding?
  answer relevancy        - is the verdict responsive to the claim?

LLM judge: the cross family audit model, never the adjudicator being scored. Embeddings: cached voyage-law-2.
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


def _build_samples(per_class: int | None, dataset_path: Path, results_path: Path) -> tuple[list, list[str]]:
    dataset = {it.id: it for it in load_dataset(dataset_path)}
    results = [json.loads(line) for line in results_path.read_text().splitlines() if line.strip()]
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
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(DATA_DIR / "briefbench_v2_dev.jsonl"))
    ap.add_argument("--results", required=True)
    ap.add_argument("--suffix", default="")
    ap.add_argument("--per-class", type=int, default=6)
    args = ap.parse_args()
    suffix = f"_{args.suffix}" if args.suffix else ""
    settings = Settings()
    samples, ids = _build_samples(args.per_class, Path(args.dataset), Path(args.results))
    if not samples:
        print(f"No adjudicated items with contexts found in {args.results}.")
        return
    print(f"Scoring {len(samples)} adjudicated briefs with RAGAS (<= {args.per_class}/class)...\n")

    llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=settings.eval_audit_model,
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
    if len(df) != len(ids):
        raise RuntimeError(f"ragas dropped rows: got {len(df)}, expected {len(ids)}")
    df.insert(0, "id", ids)
    df.to_csv(DATA_DIR / f"ragas_results{suffix}.csv", index=False)

    metric_cols = [c for c in df.columns if c not in ("id", "user_input", "retrieved_contexts", "response", "reference")]
    summary = {c: round(float(df[c].mean(skipna=True)), 4) for c in metric_cols}
    summary["n_samples"] = len(df)
    (DATA_DIR / f"ragas_summary{suffix}.json").write_text(json.dumps(summary, indent=2))

    print("\n=== RAGAS SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote ragas_results.csv and ragas_summary.json to {DATA_DIR}")


if __name__ == "__main__":
    main()

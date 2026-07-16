from __future__ import annotations

from typing import Callable

from langchain_openai import ChatOpenAI

from app.config import Settings
from app.models import ExtractionPayload, HoldingAssessment


def _chat(settings: Settings, model: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        base_url=settings.gateway_base_url,
        api_key=settings.gateway_api_key or "unset",
        temperature=0,
        timeout=120,
    )


def _require_key(settings: Settings) -> None:
    if not settings.gateway_api_key:
        raise RuntimeError("gateway key not configured")


def _invoke_structured(llm, schema, messages):
    structured = llm.with_structured_output(schema, method="function_calling")
    try:
        return structured.invoke(messages)
    except Exception:
        return structured.invoke(messages)


def make_extract_fn(settings: Settings) -> Callable[[str], ExtractionPayload]:
    def run(prompt: str) -> ExtractionPayload:
        _require_key(settings)
        return _invoke_structured(_chat(settings, settings.extraction_model), ExtractionPayload, [("user", prompt)])

    return run


def make_judge_fn(settings: Settings) -> Callable[[str, str], HoldingAssessment]:
    def run(system: str, user: str) -> HoldingAssessment:
        _require_key(settings)
        return _invoke_structured(
            _chat(settings, settings.adjudication_model), HoldingAssessment, [("system", system), ("user", user)]
        )

    return run


def make_chat_fn(settings: Settings) -> Callable[[str, str], str]:
    def run(system: str, user: str) -> str:
        _require_key(settings)
        return _chat(settings, settings.adjudication_model).invoke([("system", system), ("user", user)]).content

    return run

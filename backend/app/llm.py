from __future__ import annotations

from typing import Callable

from langchain_openai import ChatOpenAI

from app.config import Settings


def _chat(settings: Settings, model: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        base_url=settings.gateway_base_url,
        api_key=settings.gateway_api_key or "unset",
        temperature=0,
        timeout=120,
    )


def make_extract_fn(settings: Settings) -> Callable[[str], str]:
    def run(prompt: str) -> str:
        if not settings.gateway_api_key:
            raise RuntimeError("gateway key not configured")
        llm = _chat(settings, settings.extraction_model)
        return llm.invoke([("user", prompt)]).content

    return run


def make_judge_fn(settings: Settings) -> Callable[[str, str], str]:
    def run(system: str, user: str) -> str:
        if not settings.gateway_api_key:
            raise RuntimeError("gateway key not configured")
        llm = _chat(settings, settings.adjudication_model)
        return llm.invoke([("system", system), ("user", user)]).content

    return run


def make_chat_fn(settings: Settings) -> Callable[[str, str], str]:
    return make_judge_fn(settings)

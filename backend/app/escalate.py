from __future__ import annotations

import re

import httpx


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


class TavilyClient:
    def __init__(self, api_key: str, client: httpx.Client | None = None):
        self.api_key = api_key
        self._client = client or httpx.Client(timeout=30)

    def search_citation(self, citation: str, case_name: str | None) -> tuple[bool, list[str]]:
        if not self.api_key:
            return False, []
        query = f'"{citation}"' + (f" {case_name}" if case_name else "")
        try:
            r = self._client.post(
                "https://api.tavily.com/search",
                json={"api_key": self.api_key, "query": query, "max_results": 5},
            )
            r.raise_for_status()
            results = r.json().get("results", [])
        except (httpx.HTTPError, ValueError):
            return False, []
        urls = [res.get("url", "") for res in results if res.get("url")]
        needle = _norm(citation)
        for res in results:
            hay = _norm(f"{res.get('title', '')} {res.get('content', '')}")
            if needle in hay:
                return True, urls
        return False, urls

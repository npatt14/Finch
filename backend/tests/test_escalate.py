import httpx
import respx

from app.escalate import TavilyClient


@respx.mock
def test_found_when_result_mentions_citation():
    respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"title": "Brown v. Board, 347 U.S. 483", "content": "landmark case", "url": "https://x.test/a"}
                ]
            },
        )
    )
    found, urls = TavilyClient("key").search_citation("347 U.S. 483", "Brown v. Board")
    assert found is True
    assert urls == ["https://x.test/a"]


@respx.mock
def test_not_found_when_no_match():
    respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(200, json={"results": [{"title": "unrelated", "content": "nothing", "url": "https://x.test/b"}]})
    )
    found, urls = TavilyClient("key").search_citation("925 F.3d 1339", "Varghese")
    assert found is False
    assert urls == ["https://x.test/b"]


def test_missing_key_returns_not_found():
    found, urls = TavilyClient("").search_citation("1 U.S. 1", None)
    assert (found, urls) == (False, [])

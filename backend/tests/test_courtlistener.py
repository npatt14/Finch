import httpx
import respx

from app.courtlistener import CachingCourtListener, CourtListenerClient
from app.models import ExistenceStatus

BASE = "https://www.courtlistener.com/api/rest/v4"


@respx.mock
def test_resolve_found():
    respx.post(f"{BASE}/citation-lookup/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "citation": "347 U.S. 483",
                    "status": 200,
                    "clusters": [
                        {"id": 105, "absolute_url": "/opinion/105/brown/", "case_name": "Brown"}
                    ],
                }
            ],
        )
    )
    cl = CourtListenerClient(token="t")
    status, cluster_id, url = cl.resolve("347 U.S. 483")
    assert status == ExistenceStatus.FOUND
    assert cluster_id == 105
    assert url.endswith("/opinion/105/brown/")


@respx.mock
def test_resolve_not_found():
    respx.post(f"{BASE}/citation-lookup/").mock(
        return_value=httpx.Response(
            200, json=[{"citation": "925 F.3d 1339", "status": 404, "clusters": []}]
        )
    )
    status, cluster_id, url = CourtListenerClient().resolve("925 F.3d 1339")
    assert status == ExistenceStatus.NOT_FOUND
    assert cluster_id is None


@respx.mock
def test_resolve_network_error_retries_then_ambiguous(monkeypatch):
    monkeypatch.setattr("app.courtlistener.time.sleep", lambda *_: None)
    route = respx.post(f"{BASE}/citation-lookup/").mock(side_effect=httpx.ConnectError("boom"))
    status, _, _ = CourtListenerClient().resolve("347 U.S. 483")
    assert status == ExistenceStatus.AMBIGUOUS
    assert route.call_count == 4


@respx.mock
def test_resolve_retries_transient_429_then_succeeds(monkeypatch):
    monkeypatch.setattr("app.courtlistener.time.sleep", lambda *_: None)
    route = respx.post(f"{BASE}/citation-lookup/").mock(
        side_effect=[
            httpx.Response(429, headers={"retry-after": "0"}),
            httpx.Response(
                200,
                json=[{"citation": "347 U.S. 483", "status": 200,
                       "clusters": [{"id": 105, "absolute_url": "/opinion/105/brown/"}]}],
            ),
        ]
    )
    status, cid, _ = CourtListenerClient(token="t").resolve("347 U.S. 483")
    assert status == ExistenceStatus.FOUND and cid == 105
    assert route.call_count == 2


@respx.mock
def test_opinion_text_prefers_plain_text():
    respx.get(f"{BASE}/opinions/").mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"plain_text": "We hold that separate is unequal.", "html": ""}]},
        )
    )
    text = CourtListenerClient().opinion_text(105)
    assert "separate is unequal" in text


@respx.mock
def test_opinion_text_falls_back_to_html():
    respx.get(f"{BASE}/opinions/").mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"plain_text": "", "html": "<p>We <em>hold</em> X.</p>"}]},
        )
    )
    text = CourtListenerClient().opinion_text(105)
    assert "We hold X." in text


class _StubCL:
    def __init__(self, result):
        self.result = result
        self.resolve_calls = 0
        self.opinion_calls = 0
        self.year_calls = 0

    def resolve(self, citation):
        self.resolve_calls += 1
        return self.result

    def opinion_text(self, cluster_id):
        self.opinion_calls += 1
        return "opinion body"

    def case_year(self, cluster_id):
        self.year_calls += 1
        return 1954


def test_cache_serves_durable_resolve_without_refetch():
    inner = _StubCL((ExistenceStatus.FOUND, 105, "url"))
    cl = CachingCourtListener(inner)
    assert cl.resolve("347 U.S. 483") == cl.resolve("347 U.S. 483")
    assert inner.resolve_calls == 1


def test_cache_does_not_freeze_transient_ambiguous():
    inner = _StubCL((ExistenceStatus.AMBIGUOUS, None, None))
    cl = CachingCourtListener(inner)
    cl.resolve("410 U.S. 113")
    cl.resolve("410 U.S. 113")
    assert inner.resolve_calls == 2


def test_cache_reuses_opinion_and_year():
    inner = _StubCL((ExistenceStatus.FOUND, 105, "url"))
    cl = CachingCourtListener(inner)
    cl.opinion_text(105)
    cl.opinion_text(105)
    cl.case_year(105)
    cl.case_year(105)
    assert inner.opinion_calls == 1
    assert inner.year_calls == 1


@respx.mock
def test_opinion_text_prefers_majority_over_dissent():
    respx.get(f"{BASE}/opinions/").mock(
        return_value=httpx.Response(
            200,
            json={"results": [
                {"type": "040dissent", "plain_text": "I respectfully dissent."},
                {"type": "020lead", "plain_text": "We hold that separate is unequal."},
            ]},
        )
    )
    text = CourtListenerClient().opinion_text(105)
    assert text == "We hold that separate is unequal."


@respx.mock
def test_opinion_text_concatenates_when_no_majority_text():
    respx.get(f"{BASE}/opinions/").mock(
        return_value=httpx.Response(
            200,
            json={"results": [
                {"type": "040dissent", "plain_text": "I respectfully dissent."},
                {"type": "030concurrence", "plain_text": "I concur in the judgment."},
            ]},
        )
    )
    text = CourtListenerClient().opinion_text(105)
    assert "I concur in the judgment." in text
    assert "I respectfully dissent." in text

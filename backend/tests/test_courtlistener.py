import httpx
import respx

from app.courtlistener import CourtListenerClient
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
def test_resolve_network_error_is_ambiguous():
    respx.post(f"{BASE}/citation-lookup/").mock(side_effect=httpx.ConnectError("boom"))
    status, _, _ = CourtListenerClient().resolve("347 U.S. 483")
    assert status == ExistenceStatus.AMBIGUOUS


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

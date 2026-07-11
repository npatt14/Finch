import json

from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_graph import BRIEF, make_test_services


def _client():
    return TestClient(create_app(services=make_test_services()))


def test_verify_streams_ndjson_events():
    client = _client()
    with client.stream("POST", "/api/verify", data={"text": BRIEF}) as r:
        assert r.status_code == 200
        events = [json.loads(line) for line in r.iter_lines() if line]
    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert types[1] == "units"
    assert types[-1] == "done"
    assert types.count("result") == 2
    report = events[-1]["report"]
    verdicts = {res["citation"]: res["verdict"] for res in report["results"]}
    assert verdicts["925 F.3d 1339"] == "fabricated"


def test_chat_roundtrip():
    client = _client()
    with client.stream("POST", "/api/verify", data={"text": BRIEF}) as r:
        lines = [line for line in r.iter_lines() if line]
    thread_id = json.loads(lines[0])["thread_id"]
    resp = client.post("/api/chat", json={"thread_id": thread_id, "message": "Summarize the report"})
    assert resp.status_code == 200
    assert resp.json()["answer"]


def test_verify_rejects_empty():
    client = _client()
    r = client.post("/api/verify", data={"text": "   "})
    assert r.status_code == 400

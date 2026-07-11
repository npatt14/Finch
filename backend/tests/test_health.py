from fastapi.testclient import TestClient

from app.main import create_app


def test_health():
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("FINCH_GATEWAY_API_KEY", raising=False)
    from app.config import Settings

    s = Settings(_env_file=None)
    assert s.gateway_base_url == "https://ai-gateway.vercel.sh/v1"
    assert s.max_units == 40

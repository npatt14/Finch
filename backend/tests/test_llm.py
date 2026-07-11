import pytest

from app.config import Settings
from app.llm import make_extract_fn, make_judge_fn


def test_unconfigured_key_raises_at_call_time():
    s = Settings(_env_file=None, gateway_api_key="")
    fn = make_extract_fn(s)
    with pytest.raises(RuntimeError):
        fn("prompt")
    judge = make_judge_fn(s)
    with pytest.raises(RuntimeError):
        judge("sys", "user")


def test_construction_uses_settings(monkeypatch):
    captured = {}

    class FakeChat:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def invoke(self, messages):
            class R:
                content = "ok"

            return R()

    monkeypatch.setattr("app.llm.ChatOpenAI", FakeChat)
    s = Settings(_env_file=None, gateway_api_key="k", extraction_model="m1")
    fn = make_extract_fn(s)
    assert fn("hello") == "ok"
    assert captured["model"] == "m1"
    assert captured["base_url"] == s.gateway_base_url

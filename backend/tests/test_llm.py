import pytest

from app.config import Settings
from app.llm import _invoke_structured, make_chat_fn, make_extract_fn, make_judge_fn
from app.models import HoldingAssessment, HoldingStatus


class FakeStructured:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


class FakeLLM:
    def __init__(self, outcomes):
        self.structured = FakeStructured(outcomes)

    def with_structured_output(self, schema, method):
        assert method == "function_calling"
        return self.structured


def test_unconfigured_key_raises_at_call_time():
    s = Settings(_env_file=None, gateway_api_key="")
    with pytest.raises(RuntimeError):
        make_extract_fn(s)("prompt")
    with pytest.raises(RuntimeError):
        make_judge_fn(s)("sys", "user")
    with pytest.raises(RuntimeError):
        make_chat_fn(s)("sys", "user")


def test_invoke_structured_retries_once():
    good = HoldingAssessment(status=HoldingStatus.SUPPORTED, confidence=0.9)
    llm = FakeLLM([RuntimeError("bad tool call"), good])
    assert _invoke_structured(llm, HoldingAssessment, [("user", "x")]) is good
    assert llm.structured.calls == 2


def test_invoke_structured_raises_after_second_failure():
    llm = FakeLLM([RuntimeError("one"), RuntimeError("two")])
    with pytest.raises(RuntimeError):
        _invoke_structured(llm, HoldingAssessment, [("user", "x")])


def test_judge_fn_wires_model_and_schema(monkeypatch):
    created = {}

    class FakeChat:
        def __init__(self, **kwargs):
            created.update(kwargs)

        def with_structured_output(self, schema, method):
            assert schema is HoldingAssessment
            return FakeStructured([HoldingAssessment(status=HoldingStatus.SUPPORTED, confidence=1.0)])

    monkeypatch.setattr("app.llm.ChatOpenAI", FakeChat)
    s = Settings(_env_file=None, gateway_api_key="k", adjudication_model="mj")
    out = make_judge_fn(s)("sys", "user")
    assert out.status == HoldingStatus.SUPPORTED
    assert created["model"] == "mj"
    assert created["base_url"] == s.gateway_base_url


def test_chat_fn_returns_plain_text(monkeypatch):
    class FakeChat:
        def __init__(self, **kwargs):
            pass

        def invoke(self, messages):
            class R:
                content = "ok"

            return R()

    monkeypatch.setattr("app.llm.ChatOpenAI", FakeChat)
    s = Settings(_env_file=None, gateway_api_key="k")
    assert make_chat_fn(s)("sys", "user") == "ok"

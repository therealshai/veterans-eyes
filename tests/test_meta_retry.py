"""respond() never returns a truncated answer: incomplete or empty replies get
one retry with double the cap; a still-bad reply is kept only if it ends a
sentence, else it raises. All with a fake client (no credits)."""
from types import SimpleNamespace

import pytest

from backend import meta
from backend.config import SPARK_FAST


def _resp(text, status="completed", reason=None, out=50):
    return SimpleNamespace(
        output_text=text, status=status,
        incomplete_details=SimpleNamespace(reason=reason) if reason else None,
        usage=SimpleNamespace(input_tokens=10, output_tokens=out))


class _FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []  # kwargs of each responses.create

    @property
    def responses(self):
        return self

    def create(self, **kw):
        self.calls.append(kw)
        return self.replies.pop(0)


def _run(monkeypatch, replies, **kw):
    client = _FakeClient(replies)
    monkeypatch.setattr(meta, "get_client", lambda: client)
    try:
        return meta.respond("m", [meta.text_part("q")], **kw), client
    except RuntimeError as e:
        return e, client


def test_good_reply_returns_at_once(monkeypatch):
    out, client = _run(monkeypatch, [_resp("Done.")], fast=True)
    assert out == "Done." and len(client.calls) == 1


def test_incomplete_retries_with_doubled_cap(monkeypatch):
    cut = _resp("First get the", "incomplete", "max_output_tokens", out=400)
    out, client = _run(monkeypatch, [cut, _resp("First get the rag.")], fast=True)
    assert out == "First get the rag."
    cap = SPARK_FAST["max_output_tokens"]
    assert [c["max_output_tokens"] for c in client.calls] == [cap, cap * 2]


def test_empty_retries_then_returns(monkeypatch):
    out, client = _run(monkeypatch, [_resp(""), _resp("Sorry, ask again?")], fast=True)
    assert out == "Sorry, ask again?" and len(client.calls) == 2


def test_complete_sentence_kept_after_second_failure(monkeypatch):
    cut = _resp("First get the", "incomplete", "max_output_tokens", out=400)
    out, _ = _run(monkeypatch, [cut, _resp("Still fine.", "incomplete", "max_output_tokens", out=800)], fast=True)
    assert out == "Still fine."


def test_mid_sentence_after_retry_raises(monkeypatch):
    cut = _resp("First get the", "incomplete", "max_output_tokens", out=400)
    out, client = _run(monkeypatch, [cut, _resp("First get the", "incomplete", "max_output_tokens", out=800)], fast=True)
    assert isinstance(out, RuntimeError) and len(client.calls) == 2
    with pytest.raises(RuntimeError):
        raise out

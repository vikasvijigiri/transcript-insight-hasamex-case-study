import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")

import pytest
from fastapi.testclient import TestClient

from app import cache
from app.providers.types import AskResult, DocInput


class FakeProvider:
    """A stand-in Provider used in tests so no real network call is ever made.
    Configure `next_result` (or `results` for a sequence) before hitting an
    endpoint that calls it."""

    name = "fake"

    def __init__(self):
        self.calls: list[tuple[list[DocInput], str]] = []
        self.results: list[AskResult] = []
        self._default = AskResult(answer_text="A canned answer.", raw_citations=[])

    def queue(self, result: AskResult):
        self.results.append(result)

    def ask(self, docs, prompt, max_tokens=1024):
        self.calls.append((docs, prompt))
        if self.results:
            return self.results.pop(0)
        return self._default


@pytest.fixture
def fake_provider(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.main.get_provider", lambda: provider)
    return provider


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Every test gets its own empty cache directory so tests never read
    stale results from a previous run and never pollute the real cache."""
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    yield tmp_path


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)

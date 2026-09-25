from app import cache


def test_cache_key_changes_when_its_inputs_change():
    baseline = cache.build_key("expert_qa", "prompt-v1", "source-v1")
    assert baseline != cache.build_key("expert_qa", "prompt-v2", "source-v1")
    assert baseline != cache.build_key("expert_qa", "prompt-v1", "source-v2")


def test_cache_round_trip_persists_in_the_database():
    cache.write_cache("result", {"answer": "grounded", "citations": []})
    # A new process starts with an empty memory layer and must read the database.
    cache.clear_memory()
    assert cache.read_cache("result") == {"answer": "grounded", "citations": []}


def test_cache_is_shared_through_one_cache_database(tmp_path, monkeypatch):
    """Two machines with different DATABASE_URLs share results via CACHE_DATABASE_URL."""
    from app.config import get_settings

    shared = f"sqlite:///{tmp_path / 'shared-cache.db'}"
    monkeypatch.setenv("CACHE_DATABASE_URL", shared)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'laptop-a.db'}")
    get_settings.cache_clear()
    cache.write_cache("analysis", {"answer": "computed on laptop A"})

    cache.clear_memory()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'laptop-b.db'}")
    get_settings.cache_clear()
    assert cache.read_cache("analysis") == {"answer": "computed on laptop A"}


def test_rewriting_a_key_replaces_the_stored_result():
    cache.write_cache("result", {"answer": "old"})
    cache.write_cache("result", {"answer": "refreshed"})
    cache.clear_memory()
    assert cache.read_cache("result") == {"answer": "refreshed"}


def test_concurrent_identical_requests_share_one_computation():
    """Single-flight: a burst of identical uncached requests triggers one LLM call."""
    import threading
    import time

    calls = 0
    calls_guard = threading.Lock()

    def slow_llm_call():
        nonlocal calls
        with calls_guard:
            calls += 1
        time.sleep(0.2)
        return {"answer": "grounded"}

    start = threading.Barrier(20)
    results = []

    def user():
        start.wait()
        results.append(cache.get_or_compute("burst", slow_llm_call))

    threads = [threading.Thread(target=user) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert calls == 1
    assert results == [{"answer": "grounded"}] * 20


def test_failed_computation_is_not_cached():
    def failing():
        raise RuntimeError("provider outage")

    import pytest

    with pytest.raises(RuntimeError):
        cache.get_or_compute("flaky", failing)
    assert cache.read_cache("flaky") is None
    assert cache.get_or_compute("flaky", lambda: {"answer": "recovered"}) == {"answer": "recovered"}

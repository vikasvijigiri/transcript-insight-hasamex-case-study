from app import cache


def test_cache_key_changes_when_its_inputs_change():
    baseline = cache.build_key("expert_qa", "prompt-v1", "source-v1")
    assert baseline != cache.build_key("expert_qa", "prompt-v2", "source-v1")
    assert baseline != cache.build_key("expert_qa", "prompt-v1", "source-v2")


def test_cache_round_trip_is_json_and_atomic(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache.write_cache("result", {"answer": "grounded", "citations": []})
    assert cache.read_cache("result") == {"answer": "grounded", "citations": []}
    assert not list(tmp_path.glob("*.tmp"))


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

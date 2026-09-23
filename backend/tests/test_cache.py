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

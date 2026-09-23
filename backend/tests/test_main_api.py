from app.database import get_db
from app.experts import EXPERTS
from app.models import Base
from app.providers.types import AskResult, RawCitation
from app.transcript_parser import parse_transcript


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"


def test_local_mode_exposes_only_the_development_principal(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json() == {"user_id": "local", "tenant_id": "local", "roles": ["admin"]}


def test_local_browser_origin_is_allowed(client):
    response = client.options(
        "/api/experts",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


def test_metrics_endpoint_exposes_privacy_safe_rag_metrics(client):
    client.get("/api/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "hasamex_http_requests_total" in response.text
    assert "hasamex_retrieval_requests_total" in response.text
    assert "Transcript_" not in response.text


def test_authenticated_observability_dashboard_returns_aggregate_metrics(client):
    response = client.get("/api/observability")
    assert response.status_code == 200
    assert response.json().keys() == {
        "requests",
        "retrievals",
        "verifiedCitations",
        "rejectedCitations",
    }


def test_list_experts(client):
    res = client.get("/api/experts")
    assert res.status_code == 200
    ids = {e["id"] for e in res.json()}
    assert ids == {"france", "germany", "uk"}


def test_sample_corpus_import_is_tenant_scoped_and_idempotent(client):
    first = client.post("/api/projects/Robotics/sample-corpus")
    assert first.status_code == 200
    assert first.json()["imported"] == 3
    assert first.json()["already_present"] == 0
    assert set(first.json()["expert_ids"]) == {"france", "germany", "uk"}

    second = client.post("/api/projects/Robotics/sample-corpus")
    assert second.status_code == 200
    assert second.json()["imported"] == 0
    assert second.json()["already_present"] == 3


def test_transcript_endpoint_returns_the_original_source_record(client):
    res = client.get("/api/experts/france/transcript")
    assert res.status_code == 200
    body = res.json()
    assert body["expert_id"] == "france"
    assert body["expert_name"] == "Dr. Jean Martin"
    assert "00:18" in body["raw_text"]
    assert "Adoption is growing" in body["raw_text"]


def test_unknown_transcript_returns_404(client):
    assert client.get("/api/experts/atlantis/transcript").status_code == 404


def test_unknown_expert_returns_404(client, fake_provider):
    res = client.get("/api/experts/atlantis/qa")
    assert res.status_code == 404


def test_ingestion_and_hybrid_retrieval_api(client):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    app.dependency_overrides[get_db] = lambda: session
    try:
        payload = {
            "external_key": "uk-call-1",
            "filename": "uk-call-1.txt",
            "expert_id": "uk-1",
            "market": "United Kingdom",
            "raw_text": "00:00\nInterviewer: What drives adoption?\n\n00:15\nDr. Carter: Training capacity and funding determine whether adoption can grow.\n",
        }
        ingested = client.post("/api/projects/Robotics/sources", json=payload)
        assert ingested.status_code == 200
        assert ingested.json()["created"] is True

        retrieved = client.post(
            "/api/projects/Robotics/retrieve",
            json={
                "query": "What determines adoption growth?",
                "filters": {"market": "United Kingdom"},
            },
        )
        assert retrieved.status_code == 200
        assert retrieved.json()[0]["expert_id"] == "uk-1"
        assert retrieved.json()[0]["start_timestamp"] == "00:00"

        revised_payload = {
            **payload,
            "raw_text": "00:00\nInterviewer: What drives adoption?\n\n00:15\nDr. Carter: Procurement policy determines adoption decisions.\n",
        }
        revised = client.post("/api/projects/Robotics/sources", json=revised_payload)
        assert revised.status_code == 200
        assert revised.json()["created"] is True

        latest_only = client.post(
            "/api/projects/Robotics/retrieve",
            json={"query": "What determines adoption decisions?"},
        )
        assert latest_only.status_code == 200
        assert all("Training capacity" not in item["text"] for item in latest_only.json())
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_project_ask_sends_only_retrieved_context_and_validates_source_citation(
    client, fake_provider, monkeypatch
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from app.main import app

    monkeypatch.setattr("app.main.settings.rag_full_corpus_max_characters", 0)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    app.dependency_overrides[get_db] = lambda: session
    quote = "Training capacity determines adoption growth."
    try:
        session_result = client.post(
            "/api/projects/Strict-RAG/sources",
            json={
                "external_key": "call-1",
                "filename": "call-1.txt",
                "expert_id": "expert-1",
                "raw_text": "Private upload note: never send this to an LLM.\n\n00:15\nDr. Lee: Training capacity determines adoption growth.\n",
            },
        )
        assert session_result.status_code == 200
        fake_provider.queue(
            AskResult(
                answer_text="Training capacity is the stated driver.",
                raw_citations=[RawCitation(document_index=0, cited_text=quote, start_char_index=0)],
            )
        )
        response = client.post(
            "/api/projects/Strict-RAG/ask",
            json={"question": "What determines adoption growth?"},
        )
        assert response.status_code == 200
        sent_documents, _ = fake_provider.calls[-1]
        assert len(sent_documents) == 1
        assert quote in sent_documents[0].text
        assert "Private upload note" not in sent_documents[0].text
        assert response.json()["citations"][0]["timestamp"] == "00:15"
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_expert_qa_resolves_citation_to_correct_timestamp(client, fake_provider):
    # This exact sentence is real text from Transcript_1_France.txt, spoken at 02:18.
    quote = "Very important. The clinical argument may get surgeons interested"
    france_transcript = parse_transcript("france", EXPERTS[0]["file"])
    offset = france_transcript.raw_text.index(quote)

    for _ in range(6):  # one AskResult per interview-guide question
        fake_provider.queue(
            AskResult(
                answer_text="ROI matters a great deal in France.",
                raw_citations=[
                    RawCitation(document_index=0, cited_text=quote, start_char_index=offset)
                ],
            )
        )

    res = client.get("/api/experts/france/qa")
    assert res.status_code == 200
    body = res.json()
    assert body["expert_id"] == "france"
    assert len(body["answers"]) == 6
    first = body["answers"][0]
    assert first["citations"][0]["timestamp"] == "02:18"
    assert first["citations"][0]["quote"] == quote


def test_expert_qa_drops_citation_not_found_verbatim_in_source(client, fake_provider):
    for _ in range(6):
        fake_provider.queue(
            AskResult(
                answer_text="Some answer.",
                raw_citations=[
                    RawCitation(
                        document_index=0, cited_text="this sentence is invented", start_char_index=0
                    )
                ],
            )
        )

    res = client.get("/api/experts/france/qa")
    assert res.status_code == 200
    for answer in res.json()["answers"]:
        assert answer["citations"] == []


def test_expert_qa_is_cached_across_requests(client, fake_provider):
    for _ in range(6):
        fake_provider.queue(AskResult(answer_text="cached answer", raw_citations=[]))

    first = client.get("/api/experts/france/qa").json()
    # Second call should hit the disk cache, not call the provider again.
    calls_before = len(fake_provider.calls)
    second = client.get("/api/experts/france/qa").json()
    assert len(fake_provider.calls) == calls_before
    assert first == second


def test_chat_abstains_when_the_model_answer_has_no_verifiable_citation(client, fake_provider):
    fake_provider.queue(
        AskResult(
            answer_text="Adoption varies a lot by hospital size in Germany.",
            raw_citations=[],
        )
    )
    res = client.post("/api/chat", json={"question": "How does adoption vary?"})
    assert res.status_code == 200
    body = res.json()
    assert body["answer"] == "Not addressed in the indexed source material."
    assert body["citations"] == []

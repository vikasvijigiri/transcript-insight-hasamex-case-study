from app.experts import EXPERTS
from app.providers.types import AskResult, RawCitation
from app.transcript_parser import parse_transcript


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_list_experts(client):
    res = client.get("/api/experts")
    assert res.status_code == 200
    ids = {e["id"] for e in res.json()}
    assert ids == {"france", "germany", "uk"}


def test_unknown_expert_returns_404(client, fake_provider):
    res = client.get("/api/experts/atlantis/qa")
    assert res.status_code == 404


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


def test_chat_grounds_answer_with_expert_specific_citation(client, fake_provider):
    quote = "adoption is quite uneven"
    germany_transcript = parse_transcript("germany", EXPERTS[1]["file"])
    offset = germany_transcript.raw_text.index(quote)
    fake_provider.queue(
        AskResult(
            answer_text="Adoption varies a lot by hospital size in Germany.",
            raw_citations=[
                RawCitation(document_index=1, cited_text=quote, start_char_index=offset)
            ],
        )
    )
    res = client.post("/api/chat", json={"question": "How does adoption vary?"})
    assert res.status_code == 200
    body = res.json()
    assert body["citations"][0]["expert_id"] == "germany"
    assert body["citations"][0]["quote"] == quote

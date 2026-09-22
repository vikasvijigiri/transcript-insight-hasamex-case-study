from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import cache
from .config import get_settings
from .experts import EXPERTS, INTERVIEW_GUIDE_FILE, get_expert
from .interview_guide import load_questions
from .logging_config import configure_logging, get_logger
from .providers import DocInput, ProviderCallError, RawCitation, get_provider
from .schemas import (
    ChatRequest,
    ChatResponse,
    Citation,
    ExpertAnswer,
    ExpertQAResponse,
    ThemesResponse,
)
from .transcript_parser import load_transcript

# Settings() reads backend/.env itself (via pydantic-settings' env_file config), so no
# explicit load_dotenv() call is needed here.
settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

app = FastAPI(title="Hasamex Transcript Insight API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ProviderCallError)
def provider_error_handler(request: Request, exc: ProviderCallError) -> JSONResponse:
    logger.error("Provider call failed on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=502, content={"detail": str(exc)})


QUESTIONS = load_questions(INTERVIEW_GUIDE_FILE)


def verify_quote(quote: str, transcript_raw: str) -> bool:
    """Guardrail applied to every citation regardless of provider: a cited
    span must literally appear in the source transcript we sent, or we drop
    it rather than surface a possibly-mismatched quote. The OpenAI-compatible
    provider (Gemini/Groq/HF) already runs this same check once internally,
    so this is a second, cheap pass."""
    return quote.strip() in transcript_raw


def resolve_citations(raw_citations: list[RawCitation], doc_order: list[dict]) -> list[Citation]:
    resolved: list[Citation] = []
    for rc in raw_citations:
        if rc.document_index >= len(doc_order):
            continue
        expert = doc_order[rc.document_index]
        transcript = load_transcript(expert["id"], expert["file"])
        if not verify_quote(rc.cited_text, transcript.raw_text):
            continue
        resolved.append(
            Citation(
                expert_id=expert["id"],
                expert_name=expert["name"],
                quote=rc.cited_text.strip(),
                timestamp=transcript.timestamp_for_offset(rc.start_char_index),
            )
        )
    return resolved


def _doc_for(expert: dict) -> DocInput:
    transcript = load_transcript(expert["id"], expert["file"])
    return DocInput(
        expert_id=expert["id"],
        title=f"{expert['name']} ({expert['market']})",
        text=transcript.raw_text,
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "llm_provider": settings.llm_provider}


@app.get("/api/experts")
def list_experts():
    return [
        {"id": e["id"], "name": e["name"], "role": e["role"], "market": e["market"]}
        for e in EXPERTS
    ]


@app.get("/api/interview-guide")
def interview_guide():
    return {"questions": QUESTIONS}


@app.get("/api/experts/{expert_id}/qa", response_model=ExpertQAResponse)
def expert_qa(expert_id: str, refresh: bool = False):
    try:
        expert = get_expert(expert_id)
    except KeyError:
        raise HTTPException(404, f"Unknown expert '{expert_id}'") from None

    cache_key = f"qa_{expert_id}"
    if not refresh:
        cached = cache.read_cache(cache_key)
        if cached:
            return cached

    provider = get_provider()
    doc = _doc_for(expert)
    prompts = [
        (
            f'Interview-guide question: "{question}"\n\n'
            "Answer this question using ONLY what this expert said in the transcript "
            'document. If it is not addressed, answer exactly: "Not addressed in this '
            'transcript." Otherwise, answer in 1-3 concise sentences, grounded directly '
            "in a specific statement from the transcript."
        )
        for question in QUESTIONS
    ]
    # One call answering all 6 interview-guide questions at once, instead of 6
    # sequential calls — 6 calls per /qa request was enough on its own to exhaust a
    # free-tier requests-per-minute budget (Groq: 30 RPM cap hit in practice).
    results = provider.ask_batch([doc], prompts, max_tokens=3000)
    answers = []
    for question, result in zip(QUESTIONS, results, strict=True):
        citations = resolve_citations(result.raw_citations, [expert])
        answers.append(
            ExpertAnswer(question=question, answer=result.answer_text.strip(), citations=citations)
        )

    response = ExpertQAResponse(
        expert_id=expert_id,
        expert_name=expert["name"],
        role=expert["role"],
        market=expert["market"],
        answers=answers,
    )
    cache.write_cache(cache_key, response.model_dump())
    return response


@app.get("/api/themes", response_model=ThemesResponse)
def themes(refresh: bool = False):
    cache_key = "themes"
    if not refresh:
        cached = cache.read_cache(cache_key)
        if cached:
            return cached

    provider = get_provider()
    docs = [_doc_for(e) for e in EXPERTS]
    prompt = (
        "These are 3 expert-call transcripts from the same market-research project on "
        "robotic surgery adoption in Europe (France, Germany, UK). Analyse all three "
        "together and produce exactly two sections:\n\n"
        "COMMON THEMES:\n"
        "A numbered list of 3-5 points where at least two of the three experts clearly "
        "agree.\n\n"
        "DISAGREEMENTS:\n"
        "A numbered list of points where the experts' views differ meaningfully (e.g. on "
        "adoption pace, the weight of ROI/economics vs. training/clinical factors, or "
        "purchase timelines). If there is no genuine disagreement on a topic, do not "
        "invent one.\n\n"
        "Ground every point in what a specific expert actually said."
    )
    result = provider.ask(docs, prompt, max_tokens=1600)
    citations = resolve_citations(result.raw_citations, EXPERTS)

    text = result.answer_text
    common, _, disagree = text.partition("DISAGREEMENTS:")
    common = common.replace("COMMON THEMES:", "").strip()
    disagree = disagree.strip()

    response = ThemesResponse(common_themes=common, disagreements=disagree, citations=citations)
    cache.write_cache(cache_key, response.model_dump())
    return response


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    provider = get_provider()
    docs = [_doc_for(e) for e in EXPERTS]
    prompt = (
        f'Question from the research team: "{req.question}"\n\n'
        "Answer using only the 3 transcript documents provided above. If the transcripts "
        "don't contain the answer, say so explicitly instead of guessing. Ground the "
        "answer in specific statements from the relevant expert(s)."
    )
    result = provider.ask(docs, prompt, max_tokens=1000)
    citations = resolve_citations(result.raw_citations, EXPERTS)
    return ChatResponse(answer=result.answer_text.strip(), citations=citations)

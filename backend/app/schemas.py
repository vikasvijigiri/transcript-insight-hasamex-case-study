from pydantic import BaseModel, Field


class Citation(BaseModel):
    expert_id: str
    expert_name: str
    quote: str
    timestamp: str


class ExpertAnswer(BaseModel):
    question: str
    answer: str
    citations: list[Citation]


class ExpertQAResponse(BaseModel):
    expert_id: str
    expert_name: str
    role: str
    market: str
    answers: list[ExpertAnswer]
    context_mode: str = "rag_evidence"


class ThemesResponse(BaseModel):
    common_themes: str
    disagreements: str
    citations: list[Citation]
    context_mode: str = "rag_evidence"


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    context_mode: str = "rag_evidence"


class ProjectAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    filters: dict[str, str] = Field(default_factory=dict, max_length=10)


class IngestTranscriptRequest(BaseModel):
    external_key: str = Field(min_length=1, max_length=512)
    filename: str = Field(min_length=1, max_length=512)
    expert_id: str = Field(min_length=1, max_length=255)
    raw_text: str = Field(min_length=1, max_length=1_500_000)
    market: str | None = Field(default=None, max_length=128)
    role: str | None = Field(default=None, max_length=255)


class IngestionResponse(BaseModel):
    document_version_id: str
    created: bool
    turn_count: int
    passage_count: int


class SampleCorpusResponse(BaseModel):
    imported: int
    already_present: int
    expert_ids: list[str]


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    filters: dict[str, str] = Field(default_factory=dict, max_length=10)


class RetrievedEvidence(BaseModel):
    passage_id: str
    expert_id: str
    market: str | None = None
    start_timestamp: str
    end_timestamp: str
    text: str
    context: str
    score: float

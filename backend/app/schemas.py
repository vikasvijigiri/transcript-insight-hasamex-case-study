from pydantic import BaseModel


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


class ThemesResponse(BaseModel):
    common_themes: str
    disagreements: str
    citations: list[Citation]


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]

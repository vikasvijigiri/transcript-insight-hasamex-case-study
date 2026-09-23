"""Deterministic final gate for evidence-backed generated answers."""

from collections import defaultdict
from collections.abc import Mapping

from app.rag.models import GroundedResponseDraft, GroundingResult, ValidatedCitation
from app.transcript_parser import Transcript


class GroundingValidator:
    """Validates exact source spans and claim-level citation completeness.

    This is intentionally deterministic: an LLM judge may assess quality, but
    it must not be allowed to approve invented quotations or offsets.
    """

    def __init__(self, sources: Mapping[str, Transcript]) -> None:
        self.sources = sources

    def validate(self, response: GroundedResponseDraft) -> GroundingResult:
        errors: list[str] = []
        citations: list[ValidatedCitation] = []
        known_claims = {claim.id for claim in response.claims}
        cited_claims: defaultdict[str, int] = defaultdict(int)
        for draft in response.citations:
            if draft.claim_id not in known_claims:
                errors.append(f"citation references unknown claim: {draft.claim_id}")
                continue
            transcript = self.sources.get(draft.source_id)
            if transcript is None:
                errors.append(f"citation references unknown source: {draft.source_id}")
                continue
            start = self._quote_offset(transcript.raw_text, draft.quote, draft.raw_start)
            if start is None:
                errors.append(f"citation quote is not verbatim in source: {draft.source_id}")
                continue
            end = start + len(draft.quote)
            citations.append(
                ValidatedCitation(
                    claim_id=draft.claim_id,
                    source_id=draft.source_id,
                    quote=draft.quote,
                    raw_start=start,
                    raw_end=end,
                    timestamp=transcript.timestamp_for_offset(start),
                )
            )
            cited_claims[draft.claim_id] += 1
        for claim in response.claims:
            if claim.material and not cited_claims[claim.id]:
                errors.append(f"material claim has no valid citation: {claim.id}")
        return GroundingResult(valid=not errors, citations=tuple(citations), errors=tuple(errors))

    @staticmethod
    def _quote_offset(raw_text: str, quote: str, requested_start: int | None) -> int | None:
        if not quote.strip():
            return None
        if requested_start is not None:
            if (
                requested_start < 0
                or raw_text[requested_start : requested_start + len(quote)] != quote
            ):
                return None
            return requested_start
        found = raw_text.find(quote)
        return found if found >= 0 else None

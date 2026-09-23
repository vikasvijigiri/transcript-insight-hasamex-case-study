"""Optional Ragas integration with a stable local result contract.

Ragas is intentionally optional: deterministic citation checks remain
mandatory and CI must not depend on provider credentials or a judge model.
Install the optional packages documented in ``evals/README.md`` to use this
adapter in a benchmark runner.
"""

from __future__ import annotations

from typing import Any


class OptionalEvaluationDependencyError(RuntimeError):
    """Raised with an actionable install command when an optional tool is absent."""


def require_ragas() -> Any:
    """Return the Ragas module without making it a production API dependency."""

    try:
        import ragas
    except ImportError as exc:
        raise OptionalEvaluationDependencyError(
            "Ragas is optional. Install it with `pip install ragas` in the evaluation environment."
        ) from exc
    return ragas

# RAG evaluation and operations

The deterministic checks in `contracts.py` are mandatory and run in the normal
Python test suite. They verify citation offsets, citation completeness,
abstention, retrieval recall/ranking, and source/market diversity without an LLM
judge or network access.

## Golden data contract

Every production evaluation case should record:

- question, tenant/project scope, intent, and expected abstention behavior;
- the expected `evidence_id` values and source versions;
- expected market/expert coverage for comparison questions;
- a reference answer written or approved by a domain reviewer; and
- labelled negative, conflicting, and permission-denied cases.

Keep golden datasets free of production PII. Source versions must be immutable:
an evaluation result is meaningless if a citation is later evaluated against a
different transcript revision.

## Quality gates

Run deterministic tests on every pull request:

```powershell
cd backend
pytest -q
```

Run provider-backed benchmark calls only in a controlled evaluation environment:

```powershell
python -m evals.run_eval --provider gemini
```

Suggested release gates: no invalid citations, citation completeness at least
0.95 for answerable cases, correct abstention at least 0.95 for unsupported
cases, and no agreed regression in Recall@10, nDCG@10, p95 latency, or cost.
Thresholds must be calibrated against a human-reviewed dataset before becoming
release blockers.

## Optional tools

Install these in a separate evaluation image/environment, not the request API:

```powershell
pip install ragas deepeval arize-phoenix openinference-instrumentation-openai
npm install --global promptfoo
```

- **Ragas**: offline context precision/recall, faithfulness, relevance, and
  noise-sensitivity benchmark. Pair it with the deterministic checks; do not
  accept an LLM-as-judge score as citation proof.
- **DeepEval**: pytest-compatible LLM quality checks for a scheduled or
  credentialed CI evaluation stage.
- **Phoenix/OpenTelemetry**: trace ingestion, retrieval, reranking, generation,
  token use, latency, and citation-validation outcomes. Do not emit transcript
  text or personal data in traces.
- **Promptfoo**: run red-team cases, including the template in
  `promptfoo-rag.yaml`, against a staging deployment:

```powershell
cd backend/evals
promptfoo eval -c promptfoo-rag.yaml
```

## Production telemetry contract

For every query, emit a `retrieval_trace_id`, source/index/chunker/embedding
versions, filter decisions, candidate and reranker counts, selected evidence
IDs, citation-validation outcomes, model/prompt version, latency, token use,
and cost. Store protected source text separately; telemetry records identifiers
and aggregates only.

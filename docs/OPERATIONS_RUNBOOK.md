# Hasamex operations runbook

## Release gate

Do not promote a commit unless the CI and Security workflows are green, Render
reports `/api/readiness` as ready, and the authenticated browser can load one
expert profile and its cited transcript passage.

## Deployment and rollback

1. Deploy through the connected GitHub commit only; do not edit the running
   container.
2. Check Render logs for a completed Alembic migration and `/api/readiness`.
3. Check Vercel's production deployment and Google sign-in.
4. If the release fails, redeploy the last known-good Git commit in Render and
   Vercel. Do not run a database downgrade until its migration has a reviewed,
   data-safe downgrade path.

## Incident triage

1. Record the response `X-Request-ID`, UTC time, route, and affected tenant.
2. Check `/api/readiness`; a `503` indicates a dependency issue, not a browser
   session problem.
3. Inspect structured Render logs by request ID. Never paste transcripts,
   access tokens, database URLs, or provider keys into incident tickets.
4. For provider failures, return/retry later rather than bypassing RAG or
   sending a full corpus to a different provider.

## Required account-level controls before commercial launch

- Use a managed PostgreSQL backup policy and perform a documented restore test.
- Define RPO/RTO, data retention/deletion policy, and transcript processing
  consent/legal basis.
- Keep raw transcript data out of a public repository unless it is explicitly
  approved public sample content.
- Configure a central log/trace backend and alerts for readiness failures,
  sustained 5xx errors, provider failures, database saturation, and ingestion
  backlog.
- Move indexing to a durable worker/queue and persistent vector/lexical index
  before accepting high-volume uploads.
- Protect the default branch, require reviews and green checks, and use a
  staging environment before production.

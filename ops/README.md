# Live observability

The API exposes privacy-safe Prometheus metrics at `/metrics`. Metrics use only
low-cardinality route, provider, project and outcome labels. Transcript text,
questions, source text, API keys, and user identifiers are never emitted.

For the production stack, set `POSTGRES_PASSWORD` and `GRAFANA_ADMIN_PASSWORD`
in `.env.production`, then run:

```powershell
docker compose -f docker-compose.production.yml up -d
```

Open Grafana at `http://localhost:3001`; the provisioned **Hasamex RAG
Operations** dashboard includes API rate/latency, hybrid retrieval rate,
citation validation outcomes, LLM outcomes, and LLM latency. Prometheus is
available at `http://localhost:9090`.

To export traces, set `OTEL_EXPORTER_OTLP_ENDPOINT` to an OTLP/HTTP collector
endpoint (for example `http://otel-collector:4318/v1/traces`). Spans include
request route/status, RAG filter/evidence counts, and provider/model metadata,
but never prompt or transcript contents.

## Production deployment gate

Before deployment, create `.env.production` from `.env.production.example` and
replace every placeholder with secrets from a managed secret store. Set real
HTTPS application/API origins for `CORS_ORIGINS` and `NEXT_PUBLIC_API_BASE`.
The production backend runs `alembic upgrade head` before starting and disables
development schema creation. Do not expose Postgres, Redis, Prometheus, or
Grafana publicly; place the application behind a TLS reverse proxy and restrict
administrative dashboards to authenticated operators.

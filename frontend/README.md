# Hasamex frontend

The evidence workspace is a Next.js and TypeScript client for citation-backed expert research.

## Local development

Copy `.env.example` to `.env.local`, set the Supabase public values and API URL, then run:

```bash
npm install
npm run dev
```

Open http://localhost:3000.

## Quality checks

```bash
npm run lint
npx tsc --noEmit
npm test
npm run build
```

## Deployment configuration

- `NEXT_PUBLIC_API_BASE` is required for production. It must be the HTTPS public backend URL. Without it, the application shows a configuration error rather than accidentally calling a visitor's localhost.
- Configure Supabase's Site URL and allowed redirect URLs for the exact deployed frontend origin.
- `NEXT_PUBLIC_FRONTEND_OBSERVABILITY_ENDPOINT` is optional. When configured, it receives only a failure category, error name, route, and timestamp. It never receives transcript content, queries, emails, or auth tokens.
- `NEXT_PUBLIC_*` values are visible in the browser. Never put secret or service-role keys in them.

The Docker image runs as a non-root user and includes an HTTP health check. Supply the production API endpoint at build time:

```bash
docker build --build-arg NEXT_PUBLIC_API_BASE=https://api.example.com -t hasamex-frontend .
```

## Security headers

Production responses include a Content Security Policy plus clickjacking, MIME-sniffing, referrer, permissions, and HSTS protections. CSP connection permissions are built from the configured public API and Supabase origins.

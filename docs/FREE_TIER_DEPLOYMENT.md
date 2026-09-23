# Free-tier staging deployment

This is a learning/staging deployment, not a commercial production SLA. Free
tiers can suspend, impose quotas, or change terms. Keep the real application
data and secrets out of public repositories.

## Your checklist

- [ ] Create a free Supabase project; retain its URL, publishable/anon key, and
  server-only database connection string.
- [ ] In Supabase, choose an asymmetric ES256 or RS256 JWT signing key.
- [ ] In Google Cloud Console, create a **Web application** OAuth client and
  add `https://<project-ref>.supabase.co/auth/v1/callback` as its redirect URI.
- [ ] Paste the Google client ID and secret into **Supabase → Authentication →
  Providers → Google**, then enable the provider.
- [ ] Add local and Vercel URLs under **Supabase → Authentication → URL
  Configuration**.
- [ ] Deploy the API to Render and add its server-side environment secrets.
- [ ] Deploy `frontend` to Vercel and add its three `NEXT_PUBLIC_*` variables.
- [ ] Verify Google sign-in and a protected project API call.

Do not commit or expose a Google client secret, Supabase service-role key,
database password, or LLM provider key.

## 1. Create Supabase authentication and database

1. Create a free Supabase project and record its project URL and publishable
   (or anon) key.
2. In **Authentication → Providers → Google**, enable Google and paste a Google
   OAuth web-client ID and secret. Google must include Supabase's callback URL:
   `https://<project-ref>.supabase.co/auth/v1/callback`.
3. In **Authentication → URL configuration**, set the Vercel URL as Site URL,
   then add `http://localhost:3000` and the Vercel preview/production URLs as
   redirect URLs.
4. In **Authentication → JWT Signing Keys**, use an asymmetric ES256 or RS256
   key. The FastAPI service verifies signatures using the project's public JWKS;
   it never receives a Supabase service-role key.
5. Create a Postgres database connection string for the API. Do not put it in
   frontend environment variables. Before direct Supabase data access is added,
   database tables must be protected by RLS; this API already scopes every
   project ingestion/retrieval request to the verified user tenant.

## 2. Deploy the API to Render

1. Create a **Web Service** from this repository. Use the `backend/Dockerfile`.
2. Set these Render environment variables:

   - `DATABASE_URL` — Supabase Postgres connection string (server-side only;
     both `postgresql://` and `postgresql+psycopg://` are accepted)
   - `SUPABASE_URL` — e.g. `https://<project-ref>.supabase.co`
   - `SUPABASE_JWT_AUDIENCE=authenticated`
   - `AUTH_REQUIRED=true`
   - `CORS_ORIGINS=https://<your-vercel-domain>`
   - provider keys such as `GEMINI_API_KEY` (server-side only)
   - `SEED_DEMO_CORPUS=false`, `AUTO_CREATE_SCHEMA=false`

   Render injects `PORT`; the Docker image now respects it and runs Alembic
   migrations before Uvicorn starts. Run migrations deliberately in a reviewed
   deploy pipeline once multiple API instances are used.

3. Copy the Render public API URL. Confirm `<api-url>/api/health` reports
   `"authentication_required": true`.

## 3. Deploy the browser app to Vercel

1. Import this repository and select `frontend` as the root directory.
2. Set build-time environment variables:

   - `NEXT_PUBLIC_API_BASE=https://<your-render-api-domain>`
   - `NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY=<Supabase publishable or anon key>`

3. Deploy. The UI will show **Sign in with Google**. After signing in, the
   browser sends the Supabase access token to the API in `Authorization: Bearer`
   for every application request.

## Operating notes

- User data is isolated by the JWT subject by default. To give a team a shared
  workspace, set a trusted `app_metadata.tenant_id` only from server-side
  provisioning—not from editable `user_metadata`.
- The `/metrics` endpoint should be network-restricted before a public launch;
  use a private Prometheus scraper or an authenticated dashboard proxy.
- Vercel Hobby is intended for personal/non-commercial use and Render Free can
  sleep; upgrade or self-host before a commercial launch. See the official
  [Vercel Hobby documentation](https://vercel.com/docs/plans/hobby) and
  [Render free-instance documentation](https://render.com/docs/free).

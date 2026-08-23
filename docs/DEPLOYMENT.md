# Deployment (Railway)

This repo is a monorepo (`backend/`, `frontend/`), so Railway needs **two
services** in one project, each pointed at its own subdirectory, plus a
managed Postgres. Everything below except step 1 (pushing to GitHub) has to
be done by whoever owns the Railway account — API keys and billing can't be
set up by an assistant.

## 1. Push to GitHub

```bash
git push origin master
```

Railway deploys from a GitHub repo, so the code needs to be on `origin`
first (this repo already has `origin` set to
https://github.com/dleovy76-ai/yeongjong-ai).

## 2. Create the Railway project

1. https://railway.app → New Project → Deploy from GitHub repo → pick
   `yeongjong-ai`.
2. Railway will try to create one service from the repo root — delete that
   default service once the two below exist, or just add the two services
   directly and ignore it.

## 3. Add Postgres

Project → New → Database → Add PostgreSQL. Railway creates a `Postgres`
plugin with its own `DATABASE_URL` variable that the backend service
references (step 4).

Skip adding a Redis plugin — `REDIS_URL` is declared in `backend/core/config.py`
but nothing in the codebase calls Redis yet. Add it later if/when something
actually needs it.

## 4. Backend service

New service → same GitHub repo → **Settings → Root Directory: `backend`**.
Railway auto-detects the `Procfile` (`web: alembic upgrade head && uvicorn
main:app --host 0.0.0.0 --port $PORT`) — migrations run automatically on
every deploy, no separate release step needed.

Environment variables (Settings → Variables):

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (reference the Postgres plugin — the app auto-rewrites the driver prefix, see `core/config.py`'s `_with_psycopg_driver`) |
| `JWT_SECRET` | a real random value, 32+ bytes (e.g. `python -c "import secrets; print(secrets.token_urlsafe(32))"`) — **the app refuses to start in production with the placeholder default**, see `core/config.py` |
| `GEMINI_API_KEY` | real key |
| `DATA_GO_KR_API_KEY` | real key (decoded form, see `.env.example`'s note) |
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | real values (NAVER API HUB, 지역 API) |
| `FRONTEND_ORIGIN` | the frontend service's Railway URL from step 5 (comes after step 5 — see the chicken-and-egg note below) |

Settings → Networking → Generate Domain to get a public URL for this
service (needed by the frontend in step 5).

## 5. Frontend service

New service → same repo → **Settings → Root Directory: `frontend`**.
Picks up `frontend/Procfile` (`web: next start -p $PORT`).

Environment variables:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | the backend service's Railway URL from step 4 |

Generate a public domain here too.

**Chicken-and-egg**: the backend's `FRONTEND_ORIGIN` needs the frontend's
URL, and the frontend's `NEXT_PUBLIC_API_URL` needs the backend's URL — both
only exist after each service's first deploy generates a domain. Deploy both
once, copy the two generated URLs into each other's env vars, then redeploy
both (Railway redeploys automatically when you save a variable change).

## 6. Create the first admin account

Railway → backend service → the "Deploy" tab (or `railway run` via the CLI)
gives a one-off shell against the deployed environment:

```bash
python scripts/seed_admin.py --email you@example.com --password <real password> --name "운영자"
```

This is the only way to create an ADMIN account — self-registration is
deliberately blocked (`routers/auth.py`).

## 7. Verify

- `https://<backend-domain>/health` → `{"status": "ok"}`
- Register a test business owner on the frontend, create a business, confirm
  the AI chat widget responds (needs `GEMINI_API_KEY` set correctly)
- Log in as the seeded admin at `/admin`, confirm stats load

## Known gotchas already handled in code

- Railway's `DATABASE_URL` comes as plain `postgresql://` — SQLAlchemy needs
  `postgresql+psycopg://` (this project only installs psycopg3, not
  psycopg2). Auto-rewritten in `core/config.py`.
- The app hard-refuses to boot with `ENVIRONMENT=production` and the
  placeholder `JWT_SECRET` — set a real one before the first deploy or the
  backend will crash-loop with a clear error message, not a silent security
  hole.

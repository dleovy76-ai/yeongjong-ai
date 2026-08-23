# YEONGJONG AI (영종 AI)

지역 AI 경제 플랫폼 — 사장님에게는 AI 직원을, 방문객에게는 AI 여행 안내원을, 지역에는 AI 네트워크를.

전체 제품/사업 스펙은 [docs/MASTER_PLAN.md](docs/MASTER_PLAN.md), 코딩 에이전트가 지켜야 할 요약 규칙은 [CLAUDE.md](CLAUDE.md)를 참고하세요.

## Stack

- Backend: Python 3.11+, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis
- Frontend: Next.js 14 (App Router) + TypeScript + Tailwind CSS

## Local setup

### 1. Infra (Postgres + Redis)

```bash
docker compose up -d
```

### 2. Backend

```bash
cd backend
python -m venv venv
venv/Scripts/activate   # Windows; use `source venv/bin/activate` on macOS/Linux
pip install -e ".[dev]"
cp ../.env.example ../.env   # fill in real secrets
uvicorn main:app --reload
```

Backend runs at http://localhost:8000 — check http://localhost:8000/health.

Run tests:

```bash
cd backend
pytest -v
```

Run migrations (once models exist, from STEP 2 onward):

```bash
cd backend
alembic upgrade head
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:3000.

## Project status

Core loop is live locally: onboarding, Manager/Customer/Info/Expansion AI, coupons,
reservations, performance dashboard, partner graph, admin system, event tracking
(§14). Remaining from `docs/MASTER_PLAN.md` §51's dev order: Chef AI (low
priority — Customer AI already answers most menu questions), pilot deploy.
See `CLAUDE.md` / `docs/MASTER_PLAN.md` for the full dev order and non-negotiable
product rules before adding features.

## Deployment (Railway)

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the full step-by-step. Summary:
two Railway services (`backend/`, `frontend/`) in one project + a managed
Postgres plugin. Each service picks up its `Procfile` automatically. Redis is
declared in dependencies/settings but nothing in the codebase actually uses it
yet — don't provision a Redis plugin for the pilot.

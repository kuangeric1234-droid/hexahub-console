# Hexa Hub AI Marketing Agent Portal

Multi-platform AI content engine with an orchestrator + specialist agents pattern.

## Architecture

```
Brief → StrategyAgent → CalendarAgent → (per post)
        CopyAgent[platform] → VisualAgent → ComplianceAgent
        → Approval Queue → PublishingAgent
```

**Stack**
| Layer | Tech |
|---|---|
| Backend API | Python 3.11 + FastAPI |
| Agent orchestration | LangGraph |
| Task queue | Redis + Celery |
| Database | PostgreSQL 16 + pgvector |
| Object storage | MinIO (S3-compatible) |
| Frontend | Next.js 14 + TailwindCSS + shadcn/ui |

## Quick start

```bash
# 1. Copy and fill environment files
cp .env.example .env
cp backend/.env.example backend/.env      # add your LLM API keys here
cp frontend/.env.example frontend/.env

# 2. Start all infrastructure
docker compose up -d

# 3. Run database migrations (first time only)
docker compose exec backend alembic upgrade head

# 4. Verify
curl http://localhost:8000/health   # → {"status":"ok"}
open http://localhost:3001          # frontend
open http://localhost:8000/docs     # OpenAPI docs
open http://localhost:9001          # MinIO console (minioadmin / see .env)
```

## Local development (without Docker)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env                  # fill in your keys
alembic upgrade head
uvicorn main:app --reload --port 8000

# Celery worker (separate terminal)
celery -A backend.worker worker --loglevel=info

# Frontend
cd frontend
npm install
cp .env.example .env
npm run dev                           # runs on :3000
```

## Build tasks

| # | Task | Status |
|---|---|---|
| 1 | Scaffold + docker-compose + DB schema + migrations | ✅ |
| 2 | BaseAgent + LLMClient + StrategyAgent + CalendarAgent | ⏳ |
| 3 | CopyAgents (5) + VisualAgent + ComplianceAgent | ⏳ |
| 4 | LangGraph orchestrator + PublishingAgent | ⏳ |
| 5 | REST API + JWT auth | ⏳ |
| 6 | Frontend pages | ⏳ |
| 7 | End-to-end tests | ⏳ |

## Key constraints

- **No auto-publishing.** Every post goes through the approval queue.
- **No XHS/WeChat API integration.** These platforms use a "publishing package + webhook" pattern — formatted copy + assets + instructions are sent to a human operator.
- **All LLM calls** go through `LLMClient` (provider-agnostic). Each agent can be routed to a different model.
- **All agent decisions** are logged to `agent_logs` with full input/output JSON.

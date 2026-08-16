# Pi Assistant

A self-hosted personal assistant for a Raspberry Pi. It provides a React/MUI chat UI and a FastAPI service powered by the OpenAI Agents SDK. Requests can run immediately or from saved schedules, with per-agent model, reasoning, tool, and MCP selections.

The app deliberately has no authentication or multi-tenant scaling features. Keep it on a trusted network or put access controls in front of it before exposing it publicly.

## Execution modes

- **Single** — one agent produces the answer.
- **Judge** — one agent answers and a judge verifies it. A rejection sends concrete defects back to the answering agent for another attempt.
- **Jury** — one agent answers and an odd-sized jury independently votes on correctness. A failed majority sends aggregated defects back for another attempt.
- **Debate** — multiple agents debate, then a moderator synthesizes the final answer.
- **Debate + Judge** — a judge reviews the debate synthesis. Rejection triggers a remediation debate round, a new synthesis, and another review.
- **Debate + Jury** — a jury reviews the debate synthesis. A failed vote triggers remediation, resynthesis, and another jury review.

Multi-agent modes allow a different model and reasoning effort for every participant. Review modes default to three attempts and are capped at five. If every review fails, the run ends as `review_failed`; the last rejected draft remains visible in the run trace but is not presented as a successful answer.

The initial local tools are a timezone-aware current-time tool and a sandboxed arithmetic calculator. A server-owned Streamable HTTP MCP registry starts empty; configured servers appear in the UI and can be enabled by ID for each run or schedule.

## Architecture

- `frontend/`: React, TypeScript, Vite, Material UI, React Query; built into a static Nginx image.
- `backend/`: Python 3.12, FastAPI, OpenAI Agents SDK, SQLAlchemy/Alembic, APScheduler, and `uv`.
- SQLite data is stored in `backend/data/chat.db` when running locally. The production HomeLab stack persists `/app/data/chat.db` in the `chat_data` volume.
- Vite serves the SPA and proxies `/api` to the backend during local development. The production Nginx image provides the same proxy path, including server-sent run updates.

## Run locally

Create the backend environment file and configure at least one provider:

```bash
cp .env.example backend/.env
```

Start the backend:

```bash
cd backend
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

In another terminal, start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. The backend schema is available at <http://localhost:8000/api/docs>.

Useful configuration values include:

```dotenv
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OLLAMA_BASE_URL=http://olamma.tutkowski.com/v1/
APP_TIMEZONE=America/Los_Angeles
MODEL_DISCOVERY_ENABLED=true
MODEL_REFRESH_SECONDS=15
MCP_SERVERS=[]
DEFAULT_MODEL_ID=
```

Models are discovered from the configured providers and refreshed every 15 seconds. OpenAI and Gemini use their model-list APIs. Ollama uses `/api/tags`, so installed models remain selectable even when they are not currently loaded in memory. OpenAI IDs remain unprefixed, while Gemini and Ollama IDs use `gemini/...` and `ollama/...` prefixes. Multi-agent runs can mix providers per participant.

`DEFAULT_MODEL_ID` is optional. When it is empty or unavailable, the first discovered model becomes the UI default. For tests or offline recovery only, set `MODEL_DISCOVERY_ENABLED=false` and provide a comma-separated `MODEL_IDS` list.

For example, install Gemma 4 before opening the model selector:

```bash
ollama pull gemma4
```

The default Ollama server is `http://olamma.tutkowski.com`. Set `OLLAMA_BASE_URL` or `CHAT_OLLAMA_BASE_URL` to the host, a native endpoint such as `/api/generate`, or the OpenAI-compatible `/v1` endpoint; the backend normalizes all three forms. Model execution uses `/v1`, while discovery uses `/api/tags`. Do not expose an unauthenticated Ollama endpoint to the public internet.

`MCP_SERVERS` accepts a JSON array of Streamable HTTP server definitions. Headers stay server-side and are never returned by the capabilities API:

```dotenv
MCP_SERVERS=[{"id":"notes","label":"Notes","description":"Personal notes","url":"http://notes:9000/mcp","headers":{"Authorization":"Bearer replace-me"}}]
```

Vite proxies `/api` to `http://localhost:8000` during development.

The frontend API SDK is generated from FastAPI's OpenAPI schema before `dev`, `test`, and
`build`. Its output lives in `frontend/src/generated/` and is intentionally ignored by Git.
Run `npm run generate:api` to refresh it explicitly. Local generation requires `uv`; the
frontend image exports the schema in an earlier build stage.

## API overview

All application endpoints are under `/api/v1`:

- `GET /models`, `/reasoning-efforts`, `/execution-modes`, `/tools`, and `/mcp-servers`
- conversation create/list/update/delete plus message history
- `POST /runs` or `POST /conversations/{id}/runs`
- `GET /runs/{id}` and `GET /runs/{id}/events` for SSE progress
- `POST /runs/{id}/cancel`
- schedule create/list/update/delete, history, and run-now
- `GET /health/live` and `/health/ready`

The interactive OpenAPI documentation at `/api/docs` contains the full request and response schemas.

## Schedules

Schedules currently support:

- `once`: configuration such as `{ "run_at": "2026-08-12T08:00:00-07:00" }`
- `interval`: configuration such as `{ "seconds": 1800 }` (minimum 60)
- `cron`: five-field cron expressions such as `{ "expression": "0 8 * * *" }`

Each schedule stores its own timezone, prompt, execution mode, participant models, reasoning efforts, tools, MCP selections, and retry limits. The scheduler runs in the single backend process; keep one backend replica, which matches the Raspberry Pi deployment target.

## Tests and checks

```bash
cd backend
uv run ruff format --check app tests migrations
uv run ruff check app tests migrations
uv run mypy app
uv run pytest

cd ../frontend
npm test
npm run build
```

Backend orchestration tests use a deterministic fake runner, so they verify judge retries, jury majority decisions, review exhaustion, and debate remediation without spending API tokens.

## Docker publishing and HomeLab deployment

Every push to `main` runs tests and publishes ARM64-only images:

- `tutkowskim/chat-backend`
- `tutkowskim/chat-frontend`

The workflow publishes both `latest` and one shared UTC tag in `YYYY.MM.DD.HHMM` form. After both images succeed, it sends one repository dispatch to HomeLab so both pinned tags change atomically.

Configure these GitHub Actions secrets in this repository:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`
- `PERSONAL_ACCESS_TOKEN`, with permission to dispatch the `tutkowskim/HomeLab` repository

The HomeLab stack has been extended with the two services and a proxy virtual host for `chat.tutkowski.com`. Configure `CHAT_OPENAI_API_KEY` and/or `CHAT_GEMINI_API_KEY` in the Portainer stack environment. Optional values include `CHAT_GEMINI_BASE_URL`, `CHAT_OLLAMA_BASE_URL`, `CHAT_MODEL_REFRESH_SECONDS`, `CHAT_TIMEZONE`, `CHAT_MCP_SERVERS`, and `CHAT_DEFAULT_MODEL_ID`. Portainer's existing five-minute Git polling deploys the workflow's tag commit; no webhook is required.

The reusable HomeLab changes are also recorded in `deploy/HomeLab.patch`, and the service-only reference is in `deploy/homelab.compose.fragment.yml`.

## Data and recovery

Back up the `chat_data` volume, especially `chat.db`, before upgrades. To restore, stop the stack, restore that file into the volume, and start the stack again. Alembic migrations run automatically when the backend container starts.

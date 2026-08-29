# LLM Cost Autopilot

OpenAI-compatible gateway that **observes and controls** LLM spend: routing aliases, exact-response cache, budgets, usage logging, dashboard (including a **Playground** chat UI), and Python SDK.

**Full walkthrough:** [docs/TECHNICAL_TUTORIAL.md](docs/TECHNICAL_TUTORIAL.md)

## Layout

```text
apps/gateway/       FastAPI proxy + admin API
apps/dashboard/     Next.js spend UI
packages/cost-engine/
packages/shared/
packages/sdk-python/
infra/docker-compose.yml
```

## Quick start (personal)

### 1. Infrastructure

```bash
cp .env.example .env
# Personal mode works with SQLite by default (no Docker required).
# Optional: docker compose up -d postgres redis  (then switch DATABASE_URL)

cd infra
docker compose up -d postgres redis   # optional
```

### 2. Gateway

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate

pip install -e packages/cost-engine -e packages/shared -e packages/sdk-python -e apps/gateway
pip install pytest

# terminal 1
uvicorn gateway:app --reload --port 8080

# terminal 2 — seed org/project + print a virtual API key
llm-cost-seed
```

### 3. Dashboard

```bash
cd apps/dashboard
npm install
npm run dev
```

Open http://localhost:3000 — start at **Playground** (chat) or **Overview** (spend). Settings admin token defaults to `dev-secret-change-me` (`GATEWAY_SECRET`).

### 4. Call the gateway

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer <virtual-key>" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"autopilot/cheap\",\"messages\":[{\"role\":\"user\",\"content\":\"Hi\"}]}"
```

Response headers include `x-llm-cost-usd`, `x-llm-model-used`, `x-llm-cache`.

### Full Compose

```bash
cd infra
docker compose up --build
```

## Model aliases

| Alias | Default target |
|-------|----------------|
| `autopilot/cheap` | `gpt-4o-mini` |
| `autopilot/balanced` | `gpt-4o` |
| `autopilot/quality` | `claude-sonnet-4-20250514` |
| `autopilot/fast` | `gemini-2.0-flash` |

Or pass a concrete provider model id.

## Python SDK

```python
from llm_cost_sdk import AutopilotClient

with AutopilotClient(api_key="lca_...", base_url="http://localhost:8080/v1") as client:
    out = client.chat_completions(
        model="autopilot/cheap",
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(out["choices"][0]["message"]["content"])
    print(out["_autopilot"])  # cost / cache / model_used
```

OpenAI SDK drop-in:

```python
from openai import OpenAI
from llm_cost_sdk import AutopilotClient

client = OpenAI(
    api_key="lca_...",
    base_url=AutopilotClient.openai_base_url("http://localhost:8080"),
)
```

Example script: `packages/sdk-python/examples/basic_chat.py` (`LCA_API_KEY` env).

## Team SaaS mode

Same services; isolation is by `org_id` on all admin reads and usage writes.

1. Create orgs/projects via admin API (`X-Admin-Token`) or extend seed.
2. Issue per-project virtual keys.
3. Attach budgets (`alert` or `block`).
4. Members: `users` + `memberships` (`owner` / `admin` / `viewer`) — seed creates an owner; invite UI is deferred.

```bash
llm-cost-seed --org-name Acme --project-name Prod --admin-email owner@acme.test
```

## Admin API (examples)

- `GET /health`
- `POST /admin/orgs` + `POST /admin/orgs/{id}/projects`
- `POST /admin/api-keys`
- `POST /admin/budgets?org_id=`
- `GET /admin/orgs/{id}/spend`
- `GET /admin/orgs/{id}/usage`

## Tests

```bash
pytest packages/cost-engine/tests apps/gateway/tests/test_routing.py -q
```

Set `MOCK_PROVIDERS=true` on the gateway to exercise chat/cache/budgets without provider API keys.

## Success checks

- OpenAI-compatible chat via gateway with cost headers
- Dashboard shows spend shortly after a call
- Budget `block` returns HTTP 402
- Identical request returns `x-llm-cache: hit` and $0 incremental cost

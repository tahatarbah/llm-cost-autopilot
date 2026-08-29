# LLM Cost Autopilot — Full Technical Tutorial

This guide teaches the system from first principles through production use. It follows four layers: **why it exists**, **how to run it**, **how to integrate**, and **how it works inside**.

---

## Table of contents

1. [What you are building](#1-what-you-are-building)
2. [Architecture map](#2-architecture-map)
3. [Repository layout](#3-repository-layout)
4. [Prerequisites](#4-prerequisites)
5. [Hands-on tutorial: first request in 15 minutes](#5-hands-on-tutorial-first-request-in-15-minutes)
6. [Using the Playground UI](#6-using-the-playground-ui)
7. [Integrating applications](#7-integrating-applications)
8. [Budgets, cache, and routing](#8-budgets-cache-and-routing)
9. [Multi-tenant (SaaS) mode](#9-multi-tenant-saas-mode)
10. [API reference](#10-api-reference)
11. [Data model](#11-data-model)
12. [Request lifecycle (deep dive)](#12-request-lifecycle-deep-dive)
13. [Cost engine](#13-cost-engine)
14. [Configuration & environment](#14-configuration--environment)
15. [Operations & troubleshooting](#15-operations--troubleshooting)
16. [Extending the system](#16-extending-the-system)
17. [Glossary](#17-glossary)

---

## 1. What you are building

**LLM Cost Autopilot** is a **control plane for LLM spend**.

Applications stop talking to OpenAI / Anthropic / Google directly. They talk to Autopilot’s **OpenAI-compatible gateway**. The gateway:

| Capability | Behavior |
|---|---|
| **Observe** | Logs every call: tokens, USD, model, provider, latency, cache hit |
| **Route** | Maps aliases like `autopilot/cheap` to concrete provider models |
| **Cache** | Exact-match Redis cache returns prior responses at $0 provider cost |
| **Enforce** | Daily/monthly budgets can **alert** or **block** (HTTP 402) |
| **Dashboard** | Spend overview, usage log, budgets, keys, and a **Playground** chat UI |
| **SDK** | Python client that mirrors OpenAI usage patterns |

Deploy modes (same codebase):

- **Personal** — Docker Compose + env provider keys
- **Team SaaS** — orgs, projects, members, virtual keys, org-scoped data
- **Library** — `llm_cost_sdk` points at the gateway (or estimates locally)

---

## 2. Architecture map

```text
┌─────────────┐     OpenAI-compat      ┌──────────────────┐
│ App / SDK / │ ─────────────────────► │  FastAPI Gateway │
│ Playground  │   Bearer lca_…         │  /v1/chat/…      │
└─────────────┘                        └────────┬─────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    ▼                           ▼                           ▼
             ┌────────────┐              ┌────────────┐              ┌────────────┐
             │  Budget    │              │   Redis    │              │  Providers │
             │  Enforcer  │              │ Exact cache│              │ OAI/Anth/G │
             └─────┬──────┘              └────────────┘              └────────────┘
                   │
                   ▼
             ┌────────────┐     cost_engine      ┌──────────────┐
             │  Postgres  │ ◄─────────────────── │ Price table  │
             │ usage/keys │                      └──────────────┘
             └─────▲──────┘
                   │ admin API
             ┌─────┴──────┐
             │  Dashboard │
             │  Next.js   │
             └────────────┘
```

**Trust boundary:** virtual API keys authenticate *your* apps to Autopilot. Provider secrets stay on the gateway host (env vars), not in client apps.

---

## 3. Repository layout

```text
apps/
  gateway/          # FastAPI proxy, admin API, seed CLI
  dashboard/        # Next.js UI (overview, playground, budgets, keys)
packages/
  cost-engine/      # Pricing JSON + estimate/reconcile/aggregate
  shared/           # Pydantic models + settings
  sdk-python/       # AutopilotClient
infra/
  docker-compose.yml
docs/
  TECHNICAL_TUTORIAL.md   # this file
README.md
```

---

## 4. Prerequisites

- Python **3.11+**
- Node.js **20+** (dashboard)
- Docker (Postgres 16 + Redis 7)
- Optional provider keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`

Without provider keys, set `MOCK_PROVIDERS=true` to exercise the full path with canned completions.

---

## 5. Hands-on tutorial: first request in 15 minutes

### Step A — Infra (optional for local)

Personal mode defaults to **SQLite** + **in-memory cache** if Redis/Postgres are unavailable.

```bash
cd "LLM Cost Autopilot"
cp .env.example .env
# Optional hardening: docker compose for Postgres + Redis
cd infra
docker compose up -d postgres redis
# then set DATABASE_URL=postgresql+asyncpg://autopilot:autopilot@localhost:5432/autopilot in .env
```

### Step B — Python packages

```bash
cd ..
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -e packages/cost-engine -e packages/shared -e packages/sdk-python -e apps/gateway
pip install pytest
```

### Step C — Start the gateway

```bash
# dry-run without real LLM keys
set MOCK_PROVIDERS=true          # Windows PowerShell: $env:MOCK_PROVIDERS='true'
uvicorn gateway:app --reload --port 8080
```

Health check:

```bash
curl http://127.0.0.1:8080/health
```

Expected: `{"status":"ok","service":"llm-cost-autopilot"}`

### Step D — Seed org, project, and virtual key

```bash
llm-cost-seed
```

Copy the printed `lca_…` key. It is shown **once**.

Also remember:

- Admin header: `X-Admin-Token: dev-secret-change-me` (from `GATEWAY_SECRET`)

### Step E — Chat completion

```bash
curl http://127.0.0.1:8080/v1/chat/completions ^
  -H "Authorization: Bearer lca_YOUR_KEY" ^
  -H "Content-Type: application/json" ^
  -d "{\"model\":\"autopilot/cheap\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hi in one sentence.\"}]}"
```

Inspect response headers:

| Header | Meaning |
|---|---|
| `x-llm-cost-usd` | Billed USD for this call (0 on cache hit) |
| `x-llm-estimate-usd` | Pre-call estimate |
| `x-llm-model-used` | Concrete model after alias resolve |
| `x-llm-cache` | `hit` or `miss` |
| `x-llm-provider` | `openai` / `anthropic` / `google` |
| `x-llm-request-id` | Correlation id |

Send the **same** body again → expect `x-llm-cache: hit` and `x-llm-cost-usd: 0`.

### Step F — Dashboard

```bash
cd apps/dashboard
npm install
npm run dev
```

Open http://localhost:3000

1. **Settings** — confirm admin token `dev-secret-change-me`
2. **Overview** — select org **Personal**
3. **API Keys** — create a key if needed (auto-saved for Playground)
4. **Playground** — chat and watch cost/cache badges
5. **Usage** — confirm events appeared

### Step G — Python SDK

```python
from llm_cost_sdk import AutopilotClient

with AutopilotClient("lca_YOUR_KEY") as client:
    print(client.estimate("autopilot/cheap", [{"role": "user", "content": "Hi"}], remote=True))
    out = client.chat_completions(
        model="autopilot/cheap",
        messages=[{"role": "user", "content": "Hi"}],
    )
    print(out["choices"][0]["message"]["content"])
    print(out["_autopilot"])
```

OpenAI SDK drop-in:

```python
from openai import OpenAI
from llm_cost_sdk import AutopilotClient

client = OpenAI(
    api_key="lca_YOUR_KEY",
    base_url=AutopilotClient.openai_base_url("http://localhost:8080"),
)
```

### Checkpoint

You should now have:

- [x] Healthy gateway
- [x] Seeded org/project/key
- [x] Completion with cost headers
- [x] Cache hit on replay
- [x] Dashboard spend + Playground chat

---

## 6. Using the Playground UI

The Playground is the primary **human** interface to Autopilot (apps use the API/SDK).

**Flow**

1. Create a key on **API Keys** (or paste one from `llm-cost-seed`).
2. Open **Playground**.
3. Pick an alias (`autopilot/cheap` …) or a concrete model from `/v1/models`.
4. Optionally edit the system prompt.
5. Send messages. Each assistant bubble shows:
   - cache badge (`hit` / `miss`)
   - cost USD
   - resolved model
   - provider
6. Session spend accumulates at the top.
7. Pre-call estimate appears after you send (and when estimate API succeeds).

**Tips**

- Identical multi-turn prefixes with identical model/temperature/max_tokens cache by exact hash of `{model, messages, temperature, max_tokens}`.
- Budget blocks surface as errors (`402`) in the Playground error line.
- Gateway URL can be overridden in **Settings** / localStorage (`lca_gateway_url`).

---

## 7. Integrating applications

### Pattern A — Change base URL only

Any OpenAI-compatible client:

```text
base_url = http://GATEWAY:8080/v1
api_key  = lca_…
model    = autopilot/cheap   # or gpt-4o-mini, etc.
```

### Pattern B — Autopilot SDK

Use when you want cost meta without reading headers manually (`_autopilot` dict).

### Pattern C — Server-side proxy only

Keep provider keys off laptops: apps → Autopilot → providers. Rotate virtual keys per project; revoke from the dashboard.

---

## 8. Budgets, cache, and routing

### Budgets

Create via dashboard **Budgets** or:

```http
POST /admin/budgets?org_id=<uuid>
X-Admin-Token: …
Content-Type: application/json

{
  "scope": "project",
  "project_id": "<uuid>",
  "period": "monthly",
  "limit_usd": 25.0,
  "action": "block",
  "alert_threshold": 0.8
}
```

| Action | When spent ≥ limit |
|---|---|
| `alert` | Request allowed; `x-llm-budget-alert` set |
| `block` | HTTP **402** `budget_exceeded` |

Spend is summed from `usage_events` since period start (UTC day or month).

### Cache

- Backend: Redis
- Key: SHA-256 of canonical JSON `{model, messages, temperature, max_tokens}`
- TTL: `CACHE_TTL_SECONDS` (default 86400)
- Cache hits still write a usage event (`cache_hit=true`, `cost_usd=0`) for observability

### Routing aliases

Defaults:

| Alias | Target |
|---|---|
| `autopilot/cheap` | `gpt-4o-mini` |
| `autopilot/balanced` | `gpt-4o` |
| `autopilot/quality` | `claude-sonnet-4-20250514` |
| `autopilot/fast` | `gemini-2.0-flash` |

Org-specific rows in `routing_policies` override defaults. Seed inserts global defaults.

---

## 9. Multi-tenant (SaaS) mode

Same processes; isolation is by `org_id`.

1. `POST /admin/orgs` — create organization  
2. `POST /admin/orgs/{id}/projects` — create project  
3. `POST /admin/api-keys` — issue virtual key bound to project  
4. `POST /admin/orgs/{id}/members?email=…&role=admin` — attach users  
5. All usage/spend/budget queries require org id → no cross-tenant reads

Roles: `owner` | `admin` | `viewer` (stored on `memberships`; invite email UX deferred).

Seed CLI for a new tenant:

```bash
llm-cost-seed --org-name Acme --project-name Prod --admin-email owner@acme.test
```

Note: current seed uses slug `personal` for the default path; for multiple orgs prefer the admin API.

---

## 10. API reference

Base: `http://localhost:8080`

### Public / app-facing (`Authorization: Bearer lca_…`)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness |
| `POST` | `/v1/chat/completions` | OpenAI-compatible chat |
| `GET` | `/v1/models` | Aliases + priced models |
| `POST` | `/v1/estimate` | Pre-call USD estimate |
| `GET` | `/admin/meta/me` | Resolve key → org/project |

### Admin (`X-Admin-Token: <GATEWAY_SECRET>`)

| Method | Path | Purpose |
|---|---|---|
| `POST/GET` | `/admin/orgs` | Create / list orgs |
| `POST/GET` | `/admin/orgs/{id}/projects` | Projects |
| `POST` | `/admin/api-keys` | Create key (returns raw once) |
| `GET` | `/admin/orgs/{id}/api-keys` | List (prefix only) |
| `DELETE` | `/admin/api-keys/{id}` | Revoke |
| `POST` | `/admin/budgets?org_id=` | Create budget |
| `GET` | `/admin/orgs/{id}/budgets` | List + spent |
| `DELETE` | `/admin/budgets/{id}` | Delete |
| `GET` | `/admin/orgs/{id}/usage` | Recent events |
| `GET` | `/admin/orgs/{id}/spend` | Aggregates |
| `GET/POST` | `/admin/orgs/{id}/members` | Membership |

Interactive docs: http://127.0.0.1:8080/docs

### Chat body (subset)

```json
{
  "model": "autopilot/cheap",
  "messages": [{"role": "user", "content": "Hello"}],
  "temperature": 0.2,
  "max_tokens": 256,
  "stream": false
}
```

`stream: true` is rejected in v1 (`400`).

---

## 11. Data model

| Table | Role |
|---|---|
| `organizations` | Tenant |
| `users` / `memberships` | People + roles |
| `projects` | Cost/key scope inside org |
| `api_keys` | Hashed virtual keys (`sha256`) |
| `budgets` | Caps + action |
| `usage_events` | Append-only telemetry |
| `routing_policies` | Alias → model |
| `provider_configs` | Optional per-org key refs (env preferred in personal mode) |

API keys: raw `lca_` + urlsafe secret; only **hash** stored. Prefix kept for UI.

---

## 12. Request lifecycle (deep dive)

For `POST /v1/chat/completions`:

1. **Authenticate** Bearer token → `ApiKey` → `Project` → `org_id`
2. **Budget check** — sum spend in period; maybe 402
3. **Resolve model** — alias + org overrides
4. **Cache lookup** — Redis exact key
5. On hit: log zero-cost event, return cached body + `x-llm-cache: hit`
6. On miss: write `x-llm-estimate-usd`, call provider adapter
7. **Reconcile cost** via `cost_engine.reconcile_usage`
8. Persist `usage_events`, set Redis cache, return OpenAI-shaped JSON + headers

Provider adapters normalize Anthropic/Gemini responses into OpenAI chat completion shape so clients stay uniform.

---

## 13. Cost engine

Package: `packages/cost-engine`

- `prices.json` — USD per 1M input/output tokens per model
- `estimate_cost(model, in, out)` — arithmetic
- `reconcile_usage(model, usage_dict)` — maps OpenAI / Anthropic / Gemini usage fields
- `estimate_messages_tokens` — ~4 chars/token heuristic for pre-call estimates
- `aggregate_events` — group by model/project/etc.

Update prices by editing JSON and bumping `version`. Unknown models reconcile to **$0** (logged under provider `unknown`) — add them to the table before production.

Tests:

```bash
pytest packages/cost-engine/tests apps/gateway/tests -q
```

---

## 14. Configuration & environment

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | asyncpg local autopilot | Postgres |
| `REDIS_URL` | `redis://localhost:6379/0` | Cache |
| `GATEWAY_SECRET` | `dev-secret-change-me` | Admin token |
| `OPENAI_API_KEY` | empty | Provider |
| `ANTHROPIC_API_KEY` | empty | Provider |
| `GOOGLE_API_KEY` | empty | Provider |
| `MOCK_PROVIDERS` | `false` | Fake completions |
| `CORS_ORIGINS` | `http://localhost:3000` | Dashboard origin |
| `CACHE_TTL_SECONDS` | `86400` | Redis TTL |
| `NEXT_PUBLIC_GATEWAY_URL` | `http://localhost:8080` | Browser → gateway |

Full Compose (gateway + dashboard + deps):

```bash
cd infra
docker compose up --build
```

---

## 15. Operations & troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `401` on chat | Bad/revoked key | Re-seed or create key |
| `402` | Budget block | Raise limit or delete budget |
| `503` provider not configured | Missing API key | Set env or `MOCK_PROVIDERS=true` |
| Dashboard empty orgs | Never seeded | `llm-cost-seed` |
| CORS errors | Origin not allowed | Add to `CORS_ORIGINS` |
| Cache never hits | Message/model drift | Exact match only |
| Admin `401` | Wrong token | Match `GATEWAY_SECRET` |

**Observability:** prefer `x-llm-request-id` when correlating client logs with `usage_events.request_id`.

**Security checklist**

- Rotate `GATEWAY_SECRET` in any shared environment
- Never commit `.env` or raw `lca_` keys
- Revoke keys from dashboard when machines leave the team
- Keep provider keys only on the gateway host

---

## 16. Extending the system

Ideas aligned with the v1 architecture:

1. **Semantic cache** — embed messages; separate from exact Redis key  
2. **Streaming** — SSE passthrough + best-effort token accounting  
3. **Eval-based routing** — pick cheap model when quality score allows  
4. **TypeScript SDK** — mirror Python client  
5. **Stripe / billing** — charge orgs from `usage_events`  
6. **Prompt compression** — middleware before provider call  

Where to plug in:

- Routing → `gateway/routing.py` + `routing_policies`
- New provider → `gateway/providers.py` + price row
- New admin UI page → `apps/dashboard/app/…`

---

## 17. Glossary

| Term | Definition |
|---|---|
| **Virtual API key** | Autopilot-issued `lca_…` credential bound to a project |
| **Alias** | Logical model id (`autopilot/cheap`) mapped to a concrete model |
| **Exact cache** | Byte-stable request fingerprint → cached completion |
| **Reconcile** | Convert provider usage → USD via price table |
| **Control plane** | Policy + telemetry layer sitting in front of model APIs |

---

## Next steps after this tutorial

1. Put real provider keys in `.env` and turn off `MOCK_PROVIDERS`
2. Set a monthly project budget with `block`
3. Point one production app at the gateway
4. Watch **Overview** and **Usage** for a day; tune aliases toward cheaper models where quality allows

For a short operator cheat sheet, see the root [README.md](../README.md).

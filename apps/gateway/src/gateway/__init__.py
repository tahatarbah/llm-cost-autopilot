from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from llm_shared import HealthOut
from llm_shared.settings import settings

from gateway.db import init_db
from gateway.routes_admin import router as admin_router
from gateway.routes_chat import router as chat_router
from gateway.routes_meta import router as meta_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="LLM Cost Autopilot Gateway",
    version="0.2.0",
    description="OpenAI-compatible cost control plane: route, cache, budget, observe.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "x-llm-cost-usd",
        "x-llm-estimate-usd",
        "x-llm-model-used",
        "x-llm-cache",
        "x-llm-request-id",
        "x-llm-provider",
        "x-llm-budget-alert",
    ],
)

app.include_router(chat_router)
app.include_router(meta_router)
app.include_router(admin_router)


@app.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    return HealthOut()

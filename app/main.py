from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Eager initialization: validate settings on startup and warm up the agent graph.
    settings = get_settings()

    from app.agent import get_agent
    get_agent()

    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
        description=(
            "MVP of an autonomous AI agent that acts as a Junior Media Analyst, "
            "querying Google BigQuery (thelook_ecommerce) to answer questions about "
            "traffic quality and channel ROI."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "ok", "version": settings.app_version}

    return app


app = create_app()

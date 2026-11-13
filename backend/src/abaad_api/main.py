"""FastAPI application factory.

Run locally with ``make dev`` (see README). OpenAPI docs: /api/v1/docs.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import API_VERSION, get_settings
from .errors import install_error_handlers
from .routes import catalogue, compare, data, evidence, health, mission, regions

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ABAAD API",
        summary="ABAAD | أبعاد — Earth Analog Discovery Platform",
        version=API_VERSION,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(catalogue.router, prefix=API_PREFIX)
    app.include_router(regions.router, prefix=API_PREFIX)
    app.include_router(evidence.router, prefix=API_PREFIX)
    app.include_router(data.router, prefix=API_PREFIX)
    app.include_router(compare.router, prefix=API_PREFIX)
    app.include_router(mission.router, prefix=API_PREFIX)
    return app


app = create_app()

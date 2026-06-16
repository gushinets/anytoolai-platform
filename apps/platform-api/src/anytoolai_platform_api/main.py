from pathlib import Path

from fastapi import FastAPI

from anytoolai_platform_api.bootstrap import build_runtime
from anytoolai_platform_api.routers.health import router as health_router


def create_app(config_root: Path | None = None) -> FastAPI:
    runtime = build_runtime(config_root)
    app = FastAPI(title="AnytoolAI Platform API", version="0.1.0")
    app.state.runtime = runtime
    app.include_router(health_router)
    return app


app = create_app()

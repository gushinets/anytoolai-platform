from fastapi import FastAPI

from anytoolai_platform_api.routers.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="AnytoolAI Platform API", version="0.1.0")
    app.include_router(health_router)
    return app


app = create_app()

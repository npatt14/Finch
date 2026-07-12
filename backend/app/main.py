from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.routes import router


def create_app(services=None) -> FastAPI:
    settings = Settings()
    app = FastAPI(title="Finch")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin] if settings.frontend_origin != "*" else ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    config_error = None
    if services is None and settings.gateway_api_key:
        from app.services import build_services

        try:
            services = build_services(settings)
        except Exception as exc:
            config_error = str(exc)
    elif services is None:
        config_error = "no API keys configured"
    app.state.services = services
    app.state.graph = None
    app.state.config_error = config_error
    if services is not None:
        from app.graph import build_graph, make_checkpointer

        try:
            checkpointer = make_checkpointer(settings)
        except Exception as exc:
            from langgraph.checkpoint.memory import MemorySaver

            checkpointer = MemorySaver()
            if settings.database_url:
                print(f"WARNING: Postgres memory unavailable, using in-memory checkpointer: {exc}")
        app.state.graph = build_graph(services, checkpointer=checkpointer)
    app.include_router(router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()

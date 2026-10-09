from pathlib import Path
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
# routers
from api.health import router as health_router
from api.workspaces import router as workspaces_router
from api.documents import router as documents_router
from api.conversations import router as conversations_router
from api.chat import router as chats_router
from pages.index import router as index_router
from pages.workspace import router as workspace_router
#
from config.settings import settings
from starlette.staticfiles import StaticFiles
import uvicorn
import structlog

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(params: FastAPI):
    log.info("find swagger docs at http://localhost:8000/api/docs", version="1.0.0")
    yield


app = FastAPI(
    title="Pico, an RAG application",
    description="An RAG application with LangChain",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
static_dir = Path(__file__).parent / "src" / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# API routes
prefix = settings.api_prefix
app.include_router(health_router, prefix=prefix)
app.include_router(workspaces_router, prefix=prefix)
app.include_router(documents_router, prefix=prefix)
app.include_router(conversations_router, prefix=prefix)
app.include_router(chats_router, prefix=prefix)
app.include_router(index_router)
app.include_router(workspace_router, prefix=prefix)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )

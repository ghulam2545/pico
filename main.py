from pathlib import Path
from fastapi import FastAPI
from contextlib import asynccontextmanager
from pages import index as index_page
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

# Serve static files
static_dir = Path(__file__).parent / "src" / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# API routes
app.include_router(index_page.router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )

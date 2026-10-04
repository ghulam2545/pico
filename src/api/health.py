from fastapi import APIRouter
from models.health_response import HealthResponse
from service.redis_memory import RedisMemoryService
from db.session import get_async_session
from config.settings import settings
import sqlalchemy
import structlog
import asyncio
import httpx

log = structlog.get_logger()
router = APIRouter(prefix="/health", tags=["health"])

@router.get("", response_model=HealthResponse)
async def health_check():
    pg, rd, local, cloud = await asyncio.gather(
        _check_postgres(),
        _check_redis(),
        _check_ollama_local(),
        _check_ollama_cloud(),
    )
    all_up = all(s == "up" for s in [pg, rd, local, cloud])
    return HealthResponse(
        status="healthy" if all_up else "unhealthy",
        postgres=pg,
        redis=rd,
        ollama_local=local,
        ollama_cloud=cloud,
    )

async def _check_postgres() -> str:
    try:
        async with get_async_session() as session:
            await session.execute(sqlalchemy.text("SELECT 1"))
        return "up"
    except Exception as e:
        return f"down: {str(e)[:60]}"


async def _check_redis() -> str:
    try:
        ok = RedisMemoryService.ping()
        return "up" if ok else "down: ping failed"
    except Exception as e:
        return f"down: {str(e)[:60]}"


async def _check_ollama_local() -> str:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{settings.ollama_local_url}/api/tags")
            return "up" if r.status_code == 200 else f"down: HTTP {r.status_code}"
    except Exception as e:
        return f"down: {str(e)[:60]}"


async def _check_ollama_cloud() -> str:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                settings.ollama_cloud_url.rstrip("/v1") + "/v1/models",
                headers={"Authorization": f"Bearer {settings.ollama_api_key}"},
            )
            return "up" if r.status_code in (200, 401) else f"down: HTTP {r.status_code}"
    except Exception as e:
        return f"down: {str(e)[:60]}"
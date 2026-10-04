from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    postgres: str
    redis: str
    ollama_local: str
    ollama_cloud: str

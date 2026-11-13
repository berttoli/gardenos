from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field


class Settings(BaseModel):
    garden_api_base_url: str = Field(default="http://app:8000/api/v1")
    garden_api_token: str | None = None
    assistant_name: str = "GardenOS Local Assistant"


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    import os

    return Settings(
        garden_api_base_url=os.getenv("GARDEN_API_BASE_URL", "http://app:8000/api/v1"),
        garden_api_token=os.getenv("GARDEN_API_TOKEN"),
        assistant_name=os.getenv("ASSISTANT_NAME", "GardenOS Local Assistant"),
    )

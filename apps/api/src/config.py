from __future__ import annotations

import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000

    # Optional API keys (used as fallback if not provided in requests)
    openrouter_api_key: str = ""
    gemini_api_key: str = ""
    openai_api_key: str = ""

    # .env is fully optional — only load if file exists
    model_config = {
        "env_file": ".env" if os.path.isfile(".env") else None,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

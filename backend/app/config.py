import os
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    openrouter_base_url: str = os.getenv(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1",
    )
    openrouter_model: str = os.getenv(
        "OPENROUTER_MODEL",
        "google/gemini-2.5-flash-lite",
    )
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:8501")
    app_title: str = os.getenv("APP_TITLE", "Agentic Web AI")
    playwright_headed: bool = os.getenv("PLAYWRIGHT_HEADED", "false").lower() == "true"


settings = Settings()

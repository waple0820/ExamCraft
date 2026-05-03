from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
DATA_ROOT = BACKEND_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM gateway
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://litellm.local.lexmount.net/v1", alias="OPENAI_BASE_URL"
    )
    examcraft_model: str = Field(default="gpt-5.4", alias="EXAMCRAFT_MODEL")

    # gpt-image-2
    image_api_base: str = Field(default="http://10.3.47.80:4002", alias="IMAGE_API_BASE")
    image_api_key: str = Field(default="", alias="IMAGE_API_KEY")
    image_model: str = Field(default="openai/gpt-image-2", alias="IMAGE_MODEL")

    # Server
    host: str = Field(default="127.0.0.1", alias="EXAMCRAFT_HOST")
    port: int = Field(default=8000, alias="EXAMCRAFT_PORT")
    web_origin: str = Field(default="http://localhost:3000", alias="EXAMCRAFT_WEB_ORIGIN")

    # Auth
    session_secret: str = Field(default="dev-only-not-for-prod", alias="EXAMCRAFT_SESSION_SECRET")
    session_cookie_name: str = "examcraft_session"
    session_max_age_days: int = 30

    # Storage
    data_dir: Path = DATA_ROOT
    db_path: Path = DATA_ROOT / "examcraft.db"

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path}"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def pages_dir(self) -> Path:
        return self.data_dir / "pages"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        for d in (
            _settings.data_dir,
            _settings.uploads_dir,
            _settings.pages_dir,
            _settings.jobs_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
    return _settings

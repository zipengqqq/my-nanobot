from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_ENV_FILE = Path(__file__).resolve().with_name(".env")


class Settings(BaseSettings):
    """从 ``my_agent/.env`` 读取运行时配置。"""

    model_config = SettingsConfigDict(
        env_file=str(DEFAULT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_base_url: str = Field(validation_alias="OPENAI_BASE_URL")
    openai_api_key: str = Field(validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(validation_alias="OPENAI_MODEL")
    session_id: str = Field(validation_alias="MY_AGENT_SESSION_ID")
    history_limit: int = Field(validation_alias="MY_AGENT_HISTORY_LIMIT")

    @classmethod
    def from_env_file(cls, env_file: Path | str | None = None) -> "Settings":
        if env_file is None:
            return cls()
        return cls(_env_file=str(env_file))

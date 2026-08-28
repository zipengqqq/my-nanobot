from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
DEFAULT_SESSION_STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage" / "sessions"


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
    history_limit: int = Field(validation_alias="MY_AGENT_HISTORY_LIMIT")
    session_storage_dir: Path = Field(
        default=DEFAULT_SESSION_STORAGE_DIR,
        validation_alias="MY_AGENT_SESSION_STORAGE_DIR",
    )
    max_iterations: int = Field(default=6, validation_alias="MY_AGENT_MAX_ITERATIONS")
    sandbox_wsl_distro: str = Field(
        default="Ubuntu",
        validation_alias="MY_AGENT_SANDBOX_WSL_DISTRO",
    )
    sandbox_wsl_user: str = Field(
        default_factory=lambda: os.environ.get("USERNAME", ""),
        validation_alias="MY_AGENT_SANDBOX_WSL_USER",
    )
    image_api_key: str | None = Field(default=None, validation_alias="MY_AGENT_IMAGE_API_KEY")
    image_model: str = Field(default="gpt-image-2", validation_alias="MY_AGENT_IMAGE_MODEL")
    image_draw_url: str = Field(
        default="https://www.rightapi.ai/draw/v1/images/generations",
        validation_alias="MY_AGENT_IMAGE_DRAW_URL",
    )
    image_task_url_template: str = Field(
        default="https://www.rightapi.ai/v1/tasks",
        validation_alias="MY_AGENT_IMAGE_TASK_URL_TEMPLATE",
    )
    image_timeout_seconds: float = Field(
        default=120.0,
        ge=1,
        le=300,
        validation_alias="MY_AGENT_IMAGE_TIMEOUT_SECONDS",
    )
    image_max_images_per_turn: int = Field(
        default=1,
        ge=1,
        le=4,
        validation_alias="MY_AGENT_IMAGE_MAX_IMAGES_PER_TURN",
    )

    @classmethod
    def from_env_file(cls, env_file: Path | str | None = None) -> "Settings":
        if env_file is None:
            return cls()
        return cls(_env_file=str(env_file))

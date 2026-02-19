"""Application settings management."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Directory settings
    upload_dir: Path = Field(default=Path("uploads"))
    processed_dir: Path = Field(default=Path("processed"))
    processed_prefix: str = Field(default="processed_")

    # File settings
    allowed_extensions: set[str] = Field(
        default_factory=lambda: {"mp4", "avi", "mov", "mkv"}
    )
    max_upload_size: int = Field(default=524288000)  # 500MB

    # Database
    database_path: Path = Field(default=Path("data/app.db"))

    model_config = dict(
        env_prefix="VIDEO_",  # All env vars will be prefixed with VIDEO_
        case_sensitive=False,
    )

    def get_path(self, path: Path) -> Path:
        """Get absolute path if needed."""
        return path if path.is_absolute() else Path.cwd() / path


settings = Settings()

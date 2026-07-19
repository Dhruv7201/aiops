"""Configuration management using pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global library settings, loaded from env vars / .env file."""

    model_config = SettingsConfigDict(
        env_prefix="AIOPS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    debug: bool = False
    log_level: str = "INFO"
    data_dir: Path = Path("data")
    models_dir: Path = Path("models")

    # OCR defaults
    ocr_engine: str = "paddle"
    ocr_lang: str = "en"

    # Database
    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"
    mongo_url: str = "mongodb://localhost:27017"

    # YOLO
    yolo_model: str = "yolov8n.pt"
    yolo_device: str = "cpu"

    # Annotation server
    annotate_dir: Path = Path("data/annotate")
    annotate_host: str = "0.0.0.0"
    annotate_port: int = 8765


@lru_cache
def get_settings(**overrides: Any) -> Settings:
    """Return cached singleton settings instance."""
    return Settings(**overrides)

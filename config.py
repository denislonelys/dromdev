# ============================================================================
# IIStudio — Конфигурация (pydantic-settings)
# ============================================================================

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Основные ────────────────────────────────────────────────────────────
    iistudio_env: str = Field("production", alias="IISTUDIO_ENV")
    iistudio_debug: bool = Field(False, alias="IISTUDIO_DEBUG")
    iistudio_log_level: str = Field("INFO", alias="IISTUDIO_LOG_LEVEL")
    iistudio_version: str = Field("1.0.0", alias="IISTUDIO_VERSION")

    # ── API сервер ───────────────────────────────────────────────────────────
    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8080, alias="API_PORT")
    api_secret_key: str = Field("change_me_32_chars_minimum_secret", alias="API_SECRET_KEY")
    metrics_port: int = Field(9090, alias="METRICS_PORT")

    # ── Arena.ai ─────────────────────────────────────────────────────────────
    arena_email: str = Field("", alias="ARENA_EMAIL")
    arena_password: str = Field("", alias="ARENA_PASSWORD")
    arena_base_url: str = Field("https://arena.ai", alias="ARENA_BASE_URL")

    # ── PostgreSQL ───────────────────────────────────────────────────────────
    database_url: str = Field(
        "postgresql+asyncpg://iistudio:iistudio@localhost:5432/iistudio",
        alias="DATABASE_URL",
    )
    postgres_db: str = Field("iistudio", alias="POSTGRES_DB")
    postgres_user: str = Field("iistudio", alias="POSTGRES_USER")
    postgres_password: str = Field("iistudio", alias="POSTGRES_PASSWORD")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")

    # ── Redis ────────────────────────────────────────────────────────────────
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    redis_password: str = Field("", alias="REDIS_PASSWORD")
    redis_port: int = Field(6379, alias="REDIS_PORT")
    cache_ttl: int = Field(3600, alias="CACHE_TTL")
    cache_max_size: int = Field(10000, alias="CACHE_MAX_SIZE")

    # ── Прокси ───────────────────────────────────────────────────────────────
    proxy_file: str = Field("proxy.txt", alias="PROXY_FILE")
    proxy_check_interval: int = Field(300, alias="PROXY_CHECK_INTERVAL")
    proxy_max_failures: int = Field(3, alias="PROXY_MAX_FAILURES")
    mtproto_socks5_host: str = Field("127.0.0.1", alias="MTPROTO_SOCKS5_HOST")
    mtproto_socks5_port: int = Field(11080, alias="MTPROTO_SOCKS5_PORT")
    mtg_proxy_host: str = Field("tg.atomic-vpn.com", alias="MTG_PROXY_HOST")
    mtg_proxy_port: int = Field(443, alias="MTG_PROXY_PORT")
    mtg_proxy_secret: str = Field("", alias="MTG_PROXY_SECRET")

    # ── Браузер ──────────────────────────────────────────────────────────────
    browser_headless: bool = Field(True, alias="BROWSER_HEADLESS")
    browser_timeout: int = Field(60000, alias="BROWSER_TIMEOUT")
    browser_viewport_width: int = Field(1920, alias="BROWSER_VIEWPORT_WIDTH")
    browser_viewport_height: int = Field(1080, alias="BROWSER_VIEWPORT_HEIGHT")
    browser_user_agent: str = Field(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        alias="BROWSER_USER_AGENT",
    )

    # ── Оркестратор ──────────────────────────────────────────────────────────
    max_parallel_requests: int = Field(5, alias="MAX_PARALLEL_REQUESTS")
    request_timeout: int = Field(120, alias="REQUEST_TIMEOUT")
    max_retries: int = Field(3, alias="MAX_RETRIES")
    default_mode: str = Field("text", alias="DEFAULT_MODE")
    default_model: str = Field("claude-3-5-sonnet", alias="DEFAULT_MODEL")

    # ── Celery ────────────────────────────────────────────────────────────────
    celery_broker_url: str = Field("redis://localhost:6379/1", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field("redis://localhost:6379/2", alias="CELERY_RESULT_BACKEND")

    # ── Telegram уведомления ─────────────────────────────────────────────────
    telegram_bot_token: Optional[str] = Field(None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(None, alias="TELEGRAM_CHAT_ID")

    # ── SMTP ──────────────────────────────────────────────────────────────────
    smtp_host: Optional[str] = Field(None, alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    smtp_user: Optional[str] = Field(None, alias="SMTP_USER")
    smtp_pass: Optional[str] = Field(None, alias="SMTP_PASS")
    smtp_from: Optional[str] = Field(None, alias="SMTP_FROM")

    # ── 2Captcha ─────────────────────────────────────────────────────────────
    twocaptcha_api_key: Optional[str] = Field(None, alias="TWOCAPTCHA_API_KEY")

    # ── Мониторинг ───────────────────────────────────────────────────────────
    enable_metrics: bool = Field(True, alias="ENABLE_METRICS")
    enable_tracing: bool = Field(False, alias="ENABLE_TRACING")

    # ── Безопасность ─────────────────────────────────────────────────────────
    rate_limit_per_minute: int = Field(60, alias="RATE_LIMIT_PER_MINUTE")
    max_request_size_mb: int = Field(10, alias="MAX_REQUEST_SIZE_MB")
    session_ttl_hours: int = Field(24, alias="SESSION_TTL_HOURS")

    @field_validator("iistudio_log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return v

    @field_validator("default_mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        valid = {"text", "images", "video", "coding"}
        v = v.lower()
        if v not in valid:
            raise ValueError(f"default_mode must be one of {valid}")
        return v

    @property
    def proxy_file_path(self) -> Path:
        p = Path(self.proxy_file)
        if not p.is_absolute():
            p = ROOT_DIR / p
        return p

    @property
    def is_development(self) -> bool:
        return self.iistudio_env.lower() in {"development", "dev", "local"}

    @property
    def is_production(self) -> bool:
        return self.iistudio_env.lower() == "production"

    @property
    def prompt_file_path(self) -> Path:
        # поддерживаем оба варианта опечатки
        for name in ("prompt.txt", "promt.txt"):
            p = ROOT_DIR / name
            if p.exists():
                return p
        return ROOT_DIR / "prompt.txt"

    def load_system_prompt(self) -> str:
        p = self.prompt_file_path
        if p.exists():
            return p.read_text(encoding="utf-8")
        return ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Удобный алиас
settings = get_settings()

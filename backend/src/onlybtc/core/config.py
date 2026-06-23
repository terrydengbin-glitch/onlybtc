from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from onlybtc.core.paths import paths


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ONLYBTC_",
        env_file=paths.project_root / ".env",
        extra="ignore",
    )

    app_name: str = "onlyBTC"
    environment: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8118
    default_refresh_seconds: int = Field(default=600, ge=60)
    event_window_scheduler_enabled: bool = True
    event_window_scheduler_tick_seconds: int = Field(default=5, ge=1)
    event_window_cadence_profile: str = "balanced"
    event_window_manual_full_sweep_ignores_cadence: bool = True
    fred_api_key: str | None = None
    glassnode_api_key: str | None = None
    cryptoquant_api_key: str | None = None
    coinglass_api_key: str | None = None
    news_api_key: str | None = None
    source_timeout_seconds: float = Field(default=15, ge=1)
    source_http_concurrency: int = Field(default=6, ge=1)
    source_playwright_concurrency: int = Field(default=1, ge=1)
    source_official_concurrency: int = Field(default=3, ge=1)
    source_fred_concurrency: int = Field(default=3, ge=1)
    source_fred_batch_size: int = Field(default=5, ge=1)
    source_fred_inter_batch_delay_ms: int = Field(default=500, ge=0)
    source_fred_per_request_jitter_ms: int = Field(default=120, ge=0)
    source_fred_api_max_attempts: int = Field(default=3, ge=1)
    source_fred_api_backoff_seconds: float = Field(default=0.8, ge=0)
    source_max_retries: int = Field(default=1, ge=0)
    source_retry_backoff_seconds: float = Field(default=0.75, ge=0)
    source_failure_gate_threshold: int = Field(default=12, ge=0)
    source_min_current_metrics: int = Field(default=80, ge=1)

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"

    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-reasoner"
    deepseek_enable_thinking: bool = True

    qwen_api_key: str | None = None
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen3.6-max-preview"
    qwen_enable_thinking: bool = True

    volcano_api_key: str | None = None
    volcano_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    volcano_model: str = "doubao-seed-2-0-pro-260215"
    volcano_enable_thinking: bool = True

    kimi_api_key: str | None = None
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "kimi-k2.6"
    kimi_enable_thinking: bool = True

    p4_use_mock_llm: bool = True
    p4_macro_event_provider: str = "deepseek"
    p4_liquidity_flow_provider: str = "deepseek"
    p4_leverage_microstructure_provider: str = "volcano"
    p4_onchain_market_structure_provider: str = "deepseek"
    p4_cross_exam_provider: str = "deepseek"
    p4_judge_provider: str = "deepseek"
    p4_adversarial_provider: str = "deepseek"
    p4_article_provider: str = "deepseek"
    p4_llm_timeout_seconds: float = Field(default=90, ge=1)
    p4_llm_max_retries: int = Field(default=1, ge=0)
    p4_llm_max_calls_per_run: int = Field(default=32, ge=1)
    p4_llm_max_tokens_per_call: int = Field(default=4096, ge=256)
    p4_llm_temperature: float = Field(default=0.2, ge=0, le=2)
    p4_llm_max_estimated_tokens_per_run: int = Field(default=200000, ge=1000)
    p4_llm_fallback_policy: str = "fallback"

    p45_research_provider: str = "deepseek"
    p45_research_timeout_seconds: float = Field(default=180, ge=1)
    p45_research_max_retries: int = Field(default=1, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()

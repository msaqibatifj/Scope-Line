from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
ROOT = Path(__file__).resolve().parent.parent
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    host: str = '127.0.0.1'
    port: int = 8000
    model_provider: str = 'gemini'
    model_name: str = 'gemini-3.1-flash-lite'
    allowed_models: str = 'local-scripted,gemini-3.1-flash-lite,gemini-3.5-flash-lite,groq/qwen3.8-27b'
    fallback_models: str = 'groq/qwen3.8-27b'
    allow_model_fallback: bool = True
    gemini_api_key: str = ''
    gemini_base_url: str = 'https://generativelanguage.googleapis.com/v1beta/openai'
    groq_api_key: str = ''
    groq_base_url: str = 'https://api.groq.com/openai/v1'
    direct_api_free_tier: bool = True
    model_timeout_seconds: float = Field(default=10, gt=0, le=30)
    enable_live_models: bool = False
    openrouter_api_key: str = ''
    openrouter_base_url: str = 'https://openrouter.ai/api/v1'
    openrouter_site_url: str = ''
    openrouter_app_name: str = 'ScopeLine'
    max_steps: int = Field(default=6, ge=1, le=6)
    max_tool_retries: int = Field(default=2, ge=0, le=2)
    max_output_tokens: int = Field(default=512, ge=1)
    run_timeout_seconds: float = Field(default=40, gt=0, le=40)
    session_ttl_seconds: float = Field(default=1800, gt=0)
    max_history_messages: int = Field(default=12, ge=2, le=40)
    max_history_chars: int = Field(default=20000, ge=1000, le=40000)
    max_history_message_chars: int = Field(default=2000, ge=100, le=10000)
    max_external_context_chars: int = Field(default=4000, ge=100, le=10000)
    max_concurrent_chats: int = Field(default=1, ge=1, le=10)
    max_live_requests_per_minute: int = Field(default=10, ge=1, le=120)
    spend_limit_usd: float = Field(default=0, ge=0)
    allow_local_fallback: bool = False
settings = Settings()

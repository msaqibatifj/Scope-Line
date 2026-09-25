from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
ROOT = Path(__file__).resolve().parent.parent
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    host: str = '127.0.0.1'
    port: int = 8000
    model_provider: str = 'unconfigured'
    model_name: str = 'local-scripted'
    allowed_models: str = 'local-scripted'
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
    max_concurrent_chats: int = Field(default=1, ge=1, le=10)
    max_live_requests_per_minute: int = Field(default=10, ge=1, le=120)
    spend_limit_usd: float = Field(default=0, ge=0)
settings = Settings()

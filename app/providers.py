"""OpenRouter model registry and preflight controls."""
from __future__ import annotations

from collections import deque
from time import monotonic

from app.config import settings


LOCAL_MODEL = 'local-scripted'


class LiveUsageGate:
    """Process-local request-rate and cumulative-cost guard for live models."""

    def __init__(self, clock=monotonic):
        self.clock = clock
        self.started_at: deque[float] = deque()
        self.total_cost_usd = 0.0

    def admit(self, model_name: str) -> tuple[bool, str]:
        # Step 1: local runs do not consume provider capacity.
        if model_name == LOCAL_MODEL:
            return True, 'local_model'
        now = self.clock()
        while self.started_at and now - self.started_at[0] >= 60:
            self.started_at.popleft()
        if len(self.started_at) >= settings.max_live_requests_per_minute:
            return False, 'live_rate_limit_reached'
        if not model_name.endswith(':free') and self.total_cost_usd >= settings.spend_limit_usd:
            return False, 'spend_limit_reached'
        self.started_at.append(now)
        return True, 'admitted'

    def record(self, model_name: str, cost_usd: float | None) -> None:
        # Step 2: count provider-reported paid usage toward this process's cap.
        if model_name != LOCAL_MODEL and cost_usd is not None:
            self.total_cost_usd += max(0.0, cost_usd)


def allowed_model_names() -> list[str]:
    # Step 1: expose only explicitly configured model IDs.
    names = [name.strip() for name in settings.allowed_models.split(',') if name.strip()]
    if LOCAL_MODEL not in names:
        names.insert(0, LOCAL_MODEL)
    return names


def available_model_names() -> list[str]:
    # Step 2: hide live models until OpenRouter and the spend guard are enabled.
    names = [name for name in allowed_model_names() if name == LOCAL_MODEL or live_model_enabled(name)]
    return names or [LOCAL_MODEL]


def default_model_name() -> str:
    configured = settings.model_name.strip() or LOCAL_MODEL
    return configured if configured in available_model_names() else LOCAL_MODEL


def live_model_enabled(model_name: str) -> bool:
    if not settings.enable_live_models:
        return False
    if model_name == LOCAL_MODEL:
        return True
    return settings.model_provider.lower().strip() == 'openrouter' and bool(openrouter_api_key())


def model_preflight(model_name: str) -> tuple[bool, str]:
    # Step 3: reject unlisted, unfunded, or unconfigured live calls before HTTP.
    if model_name not in allowed_model_names():
        return False, 'model_not_allowed'
    if model_name == LOCAL_MODEL:
        return True, 'local_model'
    if not model_name.endswith(':free') and settings.spend_limit_usd <= 0:
        return False, 'paid_models_disabled_by_spend_limit'
    if not live_model_enabled(model_name):
        return False, 'live_model_not_configured'
    return True, 'live_model_configured'


def openrouter_api_key() -> str:
    return settings.openrouter_api_key


def is_openrouter_model(model_name: str) -> bool:
    return settings.model_provider.lower().strip() == 'openrouter' and model_name != LOCAL_MODEL


def estimate_cost_usd(model_name: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    # OpenRouter's response cost is preferred; configured free endpoints fall back to zero.
    prices = {
        'nvidia/nemotron-3-ultra-550b-a55b:free': (0.0, 0.0),
        'cohere/north-mini-code:free': (0.0, 0.0),
    }
    if model_name not in prices or input_tokens is None or output_tokens is None:
        return None
    input_price, output_price = prices[model_name]
    return round((input_tokens * input_price + output_tokens * output_price) / 1_000_000, 8)

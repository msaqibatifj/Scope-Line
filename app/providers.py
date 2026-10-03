"""Model routing, provider credentials, fallback order and usage controls."""
from __future__ import annotations

from collections import deque
import re
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
        if not is_free_model(model_name) and self.total_cost_usd >= settings.spend_limit_usd:
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
    # Step 2: hide live models until their credentials and billing policy are configured.
    names = [name for name in allowed_model_names() if model_preflight(name)[0]]
    return names or [LOCAL_MODEL]


def model_readiness() -> dict[str, object]:
    """Public, secret-free explanation of which configured model can run now."""
    configured = settings.model_name.strip() or LOCAL_MODEL
    ok, reason = model_preflight(configured)
    return {
        'configured_default': configured,
        'ready': ok,
        'reason': reason,
        'live_enabled': live_model_enabled(configured),
        'fallback_models': fallback_model_names(configured),
        'model_fallback_enabled': settings.allow_model_fallback,
        'fallback_model': LOCAL_MODEL,
        'fallback_enabled': settings.allow_local_fallback,
    }


def default_model_name() -> str:
    configured = settings.model_name.strip() or LOCAL_MODEL
    return configured if model_preflight(configured)[0] or not settings.allow_local_fallback else LOCAL_MODEL


def provider_name(model_name: str) -> str:
    if model_name == LOCAL_MODEL:
        return 'local'
    if model_name.startswith('gemini-'):
        return 'gemini'
    if model_name.startswith('groq/'):
        return 'groq'
    return 'openrouter' if settings.model_provider.lower().strip() == 'openrouter' else 'unconfigured'


def provider_connection(model_name: str) -> tuple[str, str, str]:
    """Return endpoint, credential and provider-native ID; never expose this publicly."""
    provider = provider_name(model_name)
    if provider == 'gemini':
        return settings.gemini_base_url, settings.gemini_api_key.strip(), model_name
    if provider == 'groq':
        return settings.groq_base_url, settings.groq_api_key.strip(), 'qwen/' + model_name.removeprefix('groq/')
    if provider == 'openrouter':
        return settings.openrouter_base_url, settings.openrouter_api_key.strip(), model_name
    return '', '', model_name


def is_free_model(model_name: str) -> bool:
    # A free-tier declaration requires an account without paid billing enabled.
    return model_name.endswith(':free') or (
        provider_name(model_name) in ('gemini', 'groq') and settings.direct_api_free_tier
    )


def live_model_enabled(model_name: str) -> bool:
    return bool(settings.enable_live_models and provider_connection(model_name)[1])


def fallback_model_names(model_name: str) -> list[str]:
    if not settings.allow_model_fallback:
        return []
    # Only move forward through the configured order; never cycle back to a primary.
    order = list(dict.fromkeys(name.strip() for name in settings.fallback_models.split(',') if name.strip()))
    candidates = order[order.index(model_name) + 1:] if model_name in order else order
    return [name for name in candidates if name != LOCAL_MODEL and model_preflight(name)[0]]


def model_preflight(model_name: str) -> tuple[bool, str]:
    # Step 3: reject unlisted, unfunded, or unconfigured live calls before HTTP.
    if model_name not in allowed_model_names():
        return False, 'model_not_allowed'
    if model_name == LOCAL_MODEL:
        return True, 'local_model'
    if not is_free_model(model_name) and settings.spend_limit_usd <= 0:
        return False, 'paid_models_disabled_by_spend_limit'
    if not live_model_enabled(model_name):
        return False, 'live_model_not_configured'
    return True, 'live_model_configured'


def openrouter_api_key() -> str:
    return settings.openrouter_api_key.strip()


def safe_error_message(error: Exception | str, limit: int = 500) -> str:
    """Return diagnostic detail without serializing credentials into Arena output."""
    message = str(error)
    message = re.sub(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s'\\\"]+", r'\1[redacted]', message)
    message = re.sub(r"(?i)\bbearer\s+[^\s'\\\"]+", 'Bearer [redacted]', message)
    message = re.sub(r'\b(?:gsk|sk|AIza)[A-Za-z0-9_\-]{8,}', '[redacted]', message)
    return message[:limit] or type(error).__name__


def is_openrouter_model(model_name: str) -> bool:
    return provider_name(model_name) == 'openrouter'


def estimate_cost_usd(model_name: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    if input_tokens is not None and output_tokens is not None and is_free_model(model_name):
        return 0.0
    # Preserve historical OpenRouter cost handling; unknown paid rates remain unavailable.
    prices = {
        'nvidia/nemotron-3-ultra-550b-a55b:free': (0.0, 0.0),
        'cohere/north-mini-code:free': (0.0, 0.0),
    }
    if model_name not in prices or input_tokens is None or output_tokens is None:
        return None
    input_price, output_price = prices[model_name]
    return round((input_tokens * input_price + output_tokens * output_price) / 1_000_000, 8)

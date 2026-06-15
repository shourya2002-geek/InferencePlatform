"""FastAPI dependencies: DI accessors + the auth and rate-limit chain.

Authentication and rate limiting are implemented as dependencies (not just raw
middleware) so they appear in the OpenAPI schema, are unit-testable in isolation,
and compose per-route. Together they form the gateway's "admission control":
*who* may call (auth) and *how fast* (rate limit), evaluated before any work is
enqueued.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request
from platform_common.config.settings import GatewaySettings
from platform_common.errors import RateLimitedError, UnauthorizedError

from services.api_gateway.application.submit_use_case import SubmitInferenceUseCase
from services.api_gateway.domain.rate_limiter import TokenBucketRateLimiter


def get_settings(request: Request) -> GatewaySettings:
    return request.app.state.settings


def get_use_case(request: Request) -> SubmitInferenceUseCase:
    return request.app.state.use_case


def get_rate_limiter(request: Request) -> TokenBucketRateLimiter:
    return request.app.state.rate_limiter


def require_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> str:
    """Authenticate the caller via a static API key.

    A static key list stands in for a real IdP/JWT verifier — the seam is the
    same: resolve the caller identity here, reject 401 otherwise.
    """
    settings: GatewaySettings = request.app.state.settings
    if not x_api_key or x_api_key not in settings.api_keys:
        raise UnauthorizedError("missing or invalid API key")
    return x_api_key


def enforce_rate_limit(
    api_key: Annotated[str, Depends(require_api_key)],
    request: Request,
) -> str:
    """Token-bucket rate limit, keyed by API key (runs after auth)."""
    limiter: TokenBucketRateLimiter = request.app.state.rate_limiter
    allowed, retry_after = limiter.allow(api_key)
    if not allowed:
        raise RateLimitedError(
            "rate limit exceeded for this API key", retry_after=retry_after
        )
    return api_key

"""
Security Layer — API Key auth, rate limiting, input sanitization.
Fixes from audit:
  - IP validation now uses stdlib ipaddress (not regex)
  - JWT claim removed (not implemented — honest)
  - sanitize_string blocks path traversal + null bytes
"""

from __future__ import annotations

import hmac
import ipaddress
import logging
import re
import time
from collections import defaultdict
from typing import Dict, Optional

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# ── API Key Auth ──────────────────────────────────────────────────────────

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: Optional[str] = Security(API_KEY_HEADER)) -> str:
    """FastAPI dependency — validates X-API-Key header."""
    from config.settings import settings

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Constant-time comparison — prevents timing attacks
    valid = any(hmac.compare_digest(api_key.encode(), k.encode()) for k in settings.API_KEYS)
    if not valid:
        logger.warning("Invalid API key attempt: %s...", api_key[:6])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )
    return api_key


# ── Rate Limiter ──────────────────────────────────────────────────────────


class RateLimiter:
    """
    Sliding window rate limiter per IP.
    Single-process safe (Render free tier).
    For multi-process: replace with Redis-backed implementation.
    """

    def __init__(self, requests_per_minute: int = 100, burst: int = 20) -> None:
        self.rpm = requests_per_minute
        self.burst = burst
        self._windows: Dict[str, list] = defaultdict(list)
        self._WINDOW = 60.0

    def check(self, ip: str) -> None:
        """Raise HTTP 429 if rate exceeded."""
        now = time.time()
        window = self._windows[ip]
        cutoff = now - self._WINDOW

        while window and window[0] < cutoff:
            window.pop(0)

        if len(window) >= self.rpm:
            retry_after = int(window[0] + self._WINDOW - now) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Retry after {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )
        window.append(now)

    def get_usage(self, ip: str) -> Dict:
        now = time.time()
        active = [t for t in self._windows[ip] if t >= now - self._WINDOW]
        return {
            "requests_last_minute": len(active),
            "limit": self.rpm,
            "remaining": max(0, self.rpm - len(active)),
        }


_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        from config.settings import settings

        _rate_limiter = RateLimiter(
            requests_per_minute=settings.RATE_LIMIT_PER_MINUTE,
            burst=settings.RATE_LIMIT_BURST,
        )
    return _rate_limiter


async def rate_limit_middleware(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    get_rate_limiter().check(client_ip)


# ── Input Sanitization ────────────────────────────────────────────────────

_ALPHANUM_DASH = re.compile(r"^[a-zA-Z0-9_\-\.]+$")
_COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")
_CHANNEL_VALUES = {"online", "pos", "atm", "mobile", "web"}
_CURRENCY_VALUES = {
    "USD",
    "EUR",
    "GBP",
    "INR",
    "JPY",
    "CAD",
    "AUD",
    "SGD",
    "AED",
    "CHF",
    "HKD",
    "CNY",
    "BRL",
    "MXN",
}

# Merchant categories — whitelist
_MERCHANT_CATEGORIES = {
    "grocery",
    "restaurant",
    "electronics",
    "travel",
    "pharmacy",
    "utility",
    "jewelry",
    "crypto",
    "gambling",
    "wire_transfer",
    "entertainment",
    "clothing",
    "fuel",
    "healthcare",
    "education",
    "insurance",
    "real_estate",
    "automotive",
    "unknown",
}


def sanitize_string(value: str, field_name: str, max_len: int = 100) -> str:
    """Validate and sanitize a generic ID/name string."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} cannot be empty")
    if len(value) > max_len:
        raise ValueError(f"{field_name} too long (max {max_len} chars)")
    # Block null bytes, path traversal, special chars
    if "\x00" in value or "\\" in value or "/" in value:
        raise ValueError(f"{field_name} contains invalid characters")
    if not _ALPHANUM_DASH.match(value):
        raise ValueError(f"{field_name} contains invalid characters")
    return value


def sanitize_location(location: str) -> str:
    """ISO-3166 2-letter country code."""
    loc = location.strip().upper()
    if not _COUNTRY_CODE.match(loc):
        raise ValueError(
            f"location must be 2-letter ISO country code (e.g. 'US'), got '{location}'"
        )
    return loc


def sanitize_ip(ip: str) -> str:
    """
    FIX (audit #10): Use stdlib ipaddress — not regex.
    Handles IPv4, IPv6, rejects ambiguous/malformed values.
    """
    ip = ip.strip()
    if not ip:
        raise ValueError("ip_address cannot be empty")
    try:
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        raise ValueError(f"Invalid IP address: '{ip}'")


def sanitize_channel(channel: str) -> str:
    ch = channel.strip().lower()
    if ch not in _CHANNEL_VALUES:
        raise ValueError(f"channel must be one of {sorted(_CHANNEL_VALUES)}, got '{channel}'")
    return ch


def sanitize_amount(amount: float) -> float:
    if not isinstance(amount, (int, float)):
        raise ValueError("amount must be numeric")
    amount = float(amount)
    if amount <= 0:
        raise ValueError("amount must be positive")
    if amount > 10_000_000:
        raise ValueError("amount exceeds maximum allowed ($10,000,000)")
    return round(amount, 2)


def sanitize_currency(currency: str) -> str:
    cur = currency.strip().upper()
    if cur not in _CURRENCY_VALUES:
        raise ValueError(f"currency must be one of {sorted(_CURRENCY_VALUES)}, got '{currency}'")
    return cur


def sanitize_merchant_category(category: str) -> str:
    """FIX (audit #10): merchant_category now validated against whitelist."""
    cat = category.strip().lower()
    if cat not in _MERCHANT_CATEGORIES:
        # Unknown category — normalize to 'unknown' rather than reject
        logger.warning("Unknown merchant category '%s' — normalized to 'unknown'", category)
        return "unknown"
    return cat


# ── Security Headers ──────────────────────────────────────────────────────

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Cache-Control": "no-store",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}

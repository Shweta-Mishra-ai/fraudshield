"""
Centralized configuration — all settings via environment variables.
SECURITY: In production, startup FAILS if unsafe defaults are present.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import List

_UNSAFE_API_KEYS  = {"dev-key-change-in-prod", "dev-key-local-only", "another-key", ""}
_UNSAFE_SECRETS   = {"change-me-in-production", "super-secret-change-in-production-min-32-chars", ""}


@dataclass
class Settings:
    # ── App ───────────────────────────────────────────────────────────────
    APP_NAME:    str  = "Fraud Detection API"
    APP_VERSION: str  = "2.1.0"
    ENVIRONMENT: str  = field(default_factory=lambda: os.getenv("ENVIRONMENT", "production"))
    DEBUG:       bool = field(default_factory=lambda: os.getenv("DEBUG","false").lower()=="true")
    LOG_LEVEL:   str  = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # ── API Security ──────────────────────────────────────────────────────
    API_KEY_HEADER: str     = "X-API-Key"
    API_KEYS: List[str]     = field(default_factory=lambda: [
        k.strip() for k in os.getenv("API_KEYS", "dev-key-change-in-prod").split(",") if k.strip()
    ])
    JWT_SECRET: str         = field(default_factory=lambda: os.getenv(
        "JWT_SECRET", "change-me-in-production"))
    JWT_ALGORITHM: str      = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # ── Rate Limiting ─────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT","100")))
    RATE_LIMIT_BURST: int      = 20
    BATCH_SIZE_LIMIT: int      = 100

    # ── Database ──────────────────────────────────────────────────────────
    DB_PATH: str = field(default_factory=lambda: os.getenv("DB_PATH", "data/fraud.db"))

    # ── Pathway Streaming ─────────────────────────────────────────────────
    PATHWAY_INPUT_DIR:  str = field(default_factory=lambda: os.getenv("PATHWAY_INPUT_DIR","data/transactions"))
    PATHWAY_ALERTS_DIR: str = field(default_factory=lambda: os.getenv("PATHWAY_ALERTS_DIR","data/alerts"))
    PATHWAY_MODE:       str = field(default_factory=lambda: os.getenv("PATHWAY_MODE","streaming"))

    # ── ML ────────────────────────────────────────────────────────────────
    MODEL_VERSION:       str   = "2.1.0"
    RULE_WEIGHT:         float = 0.40
    ML_WEIGHT:           float = 0.45
    GRAPH_WEIGHT:        float = 0.15
    FRAUD_THRESHOLD:     float = 0.80
    REVIEW_THRESHOLD:    float = 0.40

    # ── CORS — restrict in production ─────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = field(default_factory=lambda: [
        o.strip() for o in os.getenv(
            "ALLOWED_ORIGINS",
            # Default: only allow localhost in dev; prod MUST set this env var
            "http://localhost:8501,http://localhost:3000"
        ).split(",")
    ])

    # ── Render / Deploy ───────────────────────────────────────────────────
    PORT: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    HOST: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))

    # ── Docs exposure ─────────────────────────────────────────────────────
    ENABLE_DOCS: bool = field(default_factory=lambda: os.getenv("ENABLE_DOCS","true").lower()=="true")

    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    def is_development(self) -> bool:
        return self.ENVIRONMENT in ("development", "dev", "local")

    def validate_production_secrets(self) -> None:
        """
        SECURITY: Fail hard at startup if unsafe defaults are present in production.
        This prevents accidental deployment with placeholder credentials.
        """
        if not self.is_production():
            return  # Only enforce in production

        errors: List[str] = []

        # Check API keys
        for key in self.API_KEYS:
            if key.lower() in _UNSAFE_API_KEYS:
                errors.append(
                    f"API_KEYS contains unsafe default '{key}'. "
                    "Set a real secret in Render environment variables."
                )

        # Check JWT secret
        if self.JWT_SECRET in _UNSAFE_SECRETS:
            errors.append(
                "JWT_SECRET is an unsafe default. "
                "Set a real secret (min 32 chars) in Render environment variables."
            )

        # Check JWT secret length
        if len(self.JWT_SECRET) < 32:
            errors.append(
                f"JWT_SECRET too short ({len(self.JWT_SECRET)} chars). Minimum 32 required."
            )

        if errors:
            raise RuntimeError(
                "\n\n🚨 PRODUCTION SECURITY ERROR — Refusing to start:\n"
                + "\n".join(f"  ❌ {e}" for e in errors)
                + "\n\nSet proper secrets in your Render dashboard before deploying.\n"
            )


# Singleton — validated on import in production
settings = Settings()

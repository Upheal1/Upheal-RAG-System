"""Environment variable validation for production deployments."""

from __future__ import annotations

import os
import sys

from services.shared.logging import get_logger

logger = get_logger(__name__)

CRITICAL_VARS = ["SUPABASE_JWT_SECRET"]
WARNING_VARS = ["UPHEAL_SUPABASE_URL", "UPHEAL_SUPABASE_KEY"]
INFO_VARS = [
    "UPHEAL_CHROMA_PATH",
    "UPHEAL_CHROMA_COLLECTION",
    "UPHEAL_EMBEDDING_MODEL",
    "HOST",
    "PORT",
    "LOG_LEVEL",
]


def validate_env() -> None:
    """
    Validate critical environment variables on startup.

    - Fails hard (sys.exit) if critical vars are missing
    - Logs warnings if important vars are missing
    - Logs info for all detected configuration
    """
    # Critical: fail hard
    for var in CRITICAL_VARS:
        if not os.getenv(var):
            logger.error("env.validation.critical_missing", var=var)
            sys.exit(f"FATAL: Required environment variable {var} is not set. Refusing to start.")

    # Warnings
    for var in WARNING_VARS:
        if not os.getenv(var):
            logger.warning("env.validation.warning_missing", var=var)

    # Info log
    for var in INFO_VARS:
        val = os.getenv(var, "<not set>")
        logger.info("env.validation.config", var=var, value=val)

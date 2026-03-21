from __future__ import annotations

import logging
from typing import Optional

_configured = False


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Return a logger with a consistent formatter across services.

    Intentionally lightweight: we avoid global side effects beyond the first
    call, so unit tests remain predictable.
    """
    global _configured
    if not _configured:
        logging.basicConfig(
            level=level or logging.INFO,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )
        _configured = True
    return logging.getLogger(name)


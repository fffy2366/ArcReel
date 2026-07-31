"""Configuration helpers for AI preprocessing model calls."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("忽略非法整数环境变量 %s=%r，使用默认值 %s", name, raw, default)
        return default
    return max(minimum, value)

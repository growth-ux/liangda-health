from __future__ import annotations

import json
import logging
from typing import Any


def log_llm_request(logger: logging.Logger, *, service: str, payload: dict[str, Any]) -> None:
    logger.info(
        "llm request service=%s payload=%s",
        service,
        json.dumps(payload, ensure_ascii=False, default=str),
    )

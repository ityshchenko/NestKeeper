"""structlog JSON logging with e-mail masking. Output goes to stdout → Workers Logs."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, MutableMapping
from typing import Any, cast, no_type_check

import structlog

_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")


def mask_email(text: str) -> str:
    """Replace every e-mail in ``text`` with ``f***@domain``."""
    return _EMAIL_RE.sub(r"\1***@\2", text)


def _mask(value: Any) -> Any:
    if isinstance(value, str):
        return mask_email(value)
    if isinstance(value, Mapping):
        return {k: _mask(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_mask(v) for v in value]
    return value


def mask_emails_processor(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key, value in list(event_dict.items()):
        event_dict[key] = _mask(value)
    return event_dict


def configure_logging(level: int = logging.INFO) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            mask_emails_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


@no_type_check  # runtime checkers: the lazy proxy only becomes a FilteringBoundLogger on use
def get_logger(name: str) -> structlog.typing.FilteringBoundLogger:
    # get_logger returns a lazy proxy that binds to FilteringBoundLogger on first use.
    return cast(structlog.typing.FilteringBoundLogger, structlog.get_logger(name))

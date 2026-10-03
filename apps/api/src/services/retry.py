"""Bounded retry policy for transient provider and asset transport failures."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class RetryableHTTPError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def is_retryable_error(exc: BaseException) -> bool:
    if isinstance(exc, RetryableHTTPError):
        return exc.status_code in {408, 429, 500, 502, 503, 504}
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError)):
        return True
    text = str(exc).lower()
    return any(token in text for token in ("timeout", "timed out", "connection reset", "429", "500", "502", "503", "504"))


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 2,
    base_delay_seconds: float = 0.4,
    should_retry: Callable[[BaseException], bool] = is_retryable_error,
) -> tuple[T, int]:
    attempts = 0
    while True:
        attempts += 1
        try:
            return await operation(), attempts
        except Exception as exc:
            if attempts >= max_attempts or not should_retry(exc):
                raise
            await asyncio.sleep(base_delay_seconds * (2 ** (attempts - 1)))

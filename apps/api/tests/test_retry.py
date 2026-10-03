import asyncio

from src.services.retry import RetryableHTTPError, retry_async


def test_retry_async_retries_transient_error() -> None:
    attempts = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RetryableHTTPError(503, "temporary")
        return "ok"

    result, used = asyncio.run(retry_async(operation, max_attempts=2, base_delay_seconds=0))
    assert result == "ok"
    assert used == 2

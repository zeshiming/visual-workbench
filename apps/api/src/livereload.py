"""Live-reload for `vite build --watch` development mode.

Uses `watchfiles` (already a uvicorn dependency) to detect rebuilds
instantly — no polling delay. Notifies all connected browsers via SSE.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class LiveReload:
    """File watcher using watchfiles + SSE notification via Condition."""

    def __init__(self, dist_dir: str) -> None:
        self._dist_dir = dist_dir
        self._version = 0
        self._condition = asyncio.Condition()

    async def start(self) -> None:
        """Start watching dist/ for changes in a background task."""
        from watchfiles import awatch

        logger.info("LiveReload watching %s", self._dist_dir)
        asyncio.create_task(self._watch_loop(awatch))

    async def _watch_loop(self, awatch_fn) -> None:
        try:
            async for _changes in awatch_fn(self._dist_dir):
                async with self._condition:
                    self._version += 1
                    self._condition.notify_all()
                    logger.info("Detected rebuild (version %d)", self._version)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("watchfiles error — live-reload disabled")

    async def sse_generator(self) -> AsyncGenerator[str, None]:
        """Async generator yielding SSE `data: reload` events."""
        last_version = self._version
        try:
            while True:
                async with self._condition:
                    await self._condition.wait_for(
                        lambda: self._version != last_version
                    )
                    last_version = self._version
                yield "data: reload\n\n"
        except asyncio.CancelledError:
            pass


# ── JS snippet injected into HTML pages ────────────────────────────

AUTO_RELOAD_SCRIPT = """<script>
(function(){
  var s=new EventSource('/__reload');
  s.onmessage=function(e){if(e.data==='reload'){s.close();location.reload()}}
  s.onerror=function(){s.close();setTimeout(function(){location.reload()},800)}
})()
</script>"""


def inject_reload_script(html: str) -> str:
    """Inject the live-reload <script> before </body>."""
    if AUTO_RELOAD_SCRIPT in html:
        return html
    return html.replace("</body>", f"{AUTO_RELOAD_SCRIPT}\n</body>")

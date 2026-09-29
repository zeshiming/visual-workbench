from __future__ import annotations

import logging
import os
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import settings as app_settings
from .models.settings import init_db
from .routers import agent, editor, health, settings as settings_router, workspaces

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DEV_MODE = os.environ.get("DOUSHABAO_DEV") == "1"
DESKTOP_MODE = os.environ.get("DOUSHABAO_DESKTOP") == "1"

# ── Frontend dist path resolution ──────────────────────────────
# Priority: 1) env override (Electron desktop), 2) PyInstaller, 3) dev fallback
FRONTEND_DIST = os.environ.get("DOUSHABAO_FRONTEND_DIR") or (
    os.path.join(sys._MEIPASS, "frontend")  # pyright: ignore[reportAttributeAccessIssue]
    if getattr(sys, "frozen", False)
    else os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "web", "dist"),
    )
)


# ═════════════════════════════════════════════════════════════════

#  Custom title bar (desktop mode)
# ═════════════════════════════════════════════════════════════════

TITLEBAR_HTML = """\
<style>
:root { --titlebar-h: 40px; }
body { margin: 0; padding: 0; }
#titlebar {
  position: fixed; top: 0; left: 0; right: 0;
  height: var(--titlebar-h); z-index: 99999;
  display: flex; align-items: center;
  padding: 0 12px;
  background: #1e1e2e; color: #cdd6f4;
  user-select: none; cursor: default;
  -webkit-app-region: drag;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  font-size: 13px;
  box-sizing: border-box;
}
.is-mac #titlebar { padding-left: 80px; }
#titlebar .drag-area { flex: 1; -webkit-app-region: drag; height: 100%; }
#titlebar .tb-logo {
  display: flex; align-items: center; gap: 8px;
  -webkit-app-region: no-drag;
}
#titlebar .tb-logo .tb-dot {
  width: 20px; height: 20px; border-radius: 6px;
  background: linear-gradient(135deg, #6366f1, #a855f7);
  display: inline-flex; align-items: center; justify-content: center;
  color: white; font-weight: bold; font-size: 10px;
}
#titlebar .tb-controls {
  display: flex; align-items: center; gap: 6px;
  margin-left: 12px; -webkit-app-region: no-drag;
}
#titlebar .tb-btn {
  width: 14px; height: 14px; border-radius: 50%;
  border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; color: transparent;
  transition: color 0.15s;
}
#titlebar .tb-btn:hover { color: #1e1e2e; }
#titlebar .tb-btn.close  { background: #f38ba8; }
#titlebar .tb-btn.min   { background: #f9e2af; }
#titlebar .tb-btn.max   { background: #a6e3a1; }
</style>
<div id="titlebar">
  <div class="tb-logo">
    <span class="tb-dot">\u8c46</span>
    <strong>Doushabao</strong>
  </div>
  <div class="drag-area"></div>
  <div class="tb-controls" id="tb-controls"></div>
</div>
<div style="height:40px"></div>

<script>
(function(){
  var isMac = navigator.platform.startsWith("Mac");
  document.documentElement.classList.toggle("is-mac", isMac);

  var api = window.electronAPI;
  if (!api) return;

  var container = document.getElementById("tb-controls");
  if (!container) return;

  function makeBtn(cls, label, action) {
    var btn = document.createElement("button");
    btn.className = "tb-btn " + cls;
    btn.textContent = label;
    btn.title = cls.charAt(0).toUpperCase() + cls.slice(1);
    btn.addEventListener("click", function(e) { e.stopPropagation(); action(); });
    container.appendChild(btn);
  }

  if (!isMac) {
    makeBtn("min", "\u2500", function(){ api.minimizeWindow(); });
    makeBtn("max", "\u25a1", function(){ api.maximizeWindow(); });
    makeBtn("close", "\u2715", function(){ api.closeWindow(); });

    api.onMaximizedChanged(function(maxed){
      var maxBtn = container.querySelector(".max");
      if (maxBtn) maxBtn.textContent = maxed ? "\u2750" : "\u25a1";
    });
  }
})();
</script>
"""


def inject_titlebar(body: str) -> str:
    """Inject custom title bar right after <body>."""
    idx = body.find("<body")
    if idx == -1:
        return body
    close_bracket = body.find(">", idx)
    if close_bracket == -1:
        return body
    insert_at = close_bracket + 1
    return body[:insert_at] + "\n" + TITLEBAR_HTML + "\n" + body[insert_at:]


# ═════════════════════════════════════════════════════════════════
#  App factory
# ═════════════════════════════════════════════════════════════════

# ── API paths that should NOT be caught by the SPA fallback ─────
_SPA_EXCLUDED_PREFIXES = ("/api/", "/health", "/docs", "/openapi.json", "/redoc")


def _create_app() -> FastAPI:
    app = FastAPI(
        title="Doushabao API",
        version="0.1.0",
        description="Backend service for Doushabao AI Image Editor",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(agent.router)
    app.include_router(editor.router)
    app.include_router(settings_router.router)
    app.include_router(workspaces.router)

    if os.path.isdir(FRONTEND_DIST):
        # ── Desktop mode: inject custom title bar ─────────────
        if DESKTOP_MODE:

            @app.middleware("http")
            async def inject_desktop_titlebar(request, call_next):
                response = await call_next(request)
                if isinstance(response, HTMLResponse):
                    body = response.body.decode("utf-8")
                    if "<body" in body:
                        return HTMLResponse(
                            inject_titlebar(body),
                            status_code=response.status_code,
                            headers=dict(response.headers),
                        )
                return response

        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True))
        logger.info("Serving frontend from %s", FRONTEND_DIST)

        # ── SPA fallback: serve index.html for non-API 404s ────
        @app.middleware("http")
        async def spa_fallback(request, call_next):
            response = await call_next(request)
            if response.status_code == 404 and not request.url.path.startswith(
                _SPA_EXCLUDED_PREFIXES,
            ):
                index_path = os.path.join(FRONTEND_DIST, "index.html")
                if os.path.isfile(index_path):
                    return FileResponse(index_path, media_type="text/html")
            return response

    else:
        if DEV_MODE:
            logger.warning("Dev mode: frontend dist not found — frontend not available")
        else:
            logger.info("No frontend build found — API-only mode")

    @app.on_event("startup")
    async def startup():
        logger.info("Doushabao API starting up...")
        init_db()

    @app.on_event("shutdown")
    async def shutdown():
        logger.info("Doushabao API shutting down...")

    return app


app = _create_app()


def start():
    """Entry point for PyInstaller-frozen app and direct CLI usage."""
    uvicorn.run(
        app,  # module-level app instance, works in frozen PyInstaller too
        host=app_settings.host,
        port=app_settings.port,
        reload=not DESKTOP_MODE,
    )


if __name__ == "__main__":
    start()

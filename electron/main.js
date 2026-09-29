const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");
const net = require("net");
const fs = require("fs");
const { ipcMain, shell } = require("electron");

// ── Detect platform ─────────────────────────────────────────────
const IS_MAC = process.platform === "darwin";
const IS_WIN = process.platform === "win32";

// ── Single instance lock ────────────────────────────────────────
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
}

// ── Constants ────────────────────────────────────────────────────
const DEV_MODE = !app.isPackaged;
const BACKEND_HOST = "127.0.0.1";
const BACKEND_PORT_START = 18000;
const SERVER_READY_TIMEOUT = 30_000; // 30 seconds

let mainWindow = null;
let backendProcess = null;
let actualPort = BACKEND_PORT_START;

// ═════════════════════════════════════════════════════════════════
//  Port / server utilities
// ═════════════════════════════════════════════════════════════════

/** Find an available TCP port starting from `start`. */
function findAvailablePort(start) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(start, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

/** Poll GET /health until the backend responds or timeout. */
function waitForServer(port, timeout) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeout;
    function poll() {
      const req = http.get(
        `http://127.0.0.1:${port}/health`,
        (res) => {
          res.resume();
          resolve(port);
        },
      );
      req.on("error", () => {
        if (Date.now() > deadline) {
          reject(new Error(`后端服务未能在 ${timeout / 1000}s 内启动`));
        } else {
          setTimeout(poll, 300);
        }
      });
      req.end();
    }
    poll();
  });
}

// ═════════════════════════════════════════════════════════════════
//  Backend process management
// ═════════════════════════════════════════════════════════════════

/** Resolve paths for the backend binary & frontend dist. */
function resolvePaths() {
  if (app.isPackaged) {
    // Production: extraResources copied alongside app
    const res = process.resourcesPath;
    const plat = process.platform;
    const ext = plat === "win32" ? ".exe" : "";
    return {
      backend: path.join(res, "backend", `doushabao-api${ext}`),
      frontend: path.join(res, "frontend"),
    };
  }
  // Development: use project source
  const root = path.join(__dirname, "..");
  return {
    backend: null, // will use uv
    frontend: path.join(root, "apps", "web", "dist"),
  };
}

function startBackend(port) {
  return new Promise((resolve, reject) => {
    const { backend: backendPath, frontend: frontendPath } = resolvePaths();
    const env = {
      ...process.env,
      HOST: BACKEND_HOST,
      PORT: String(port),
      DOUSHABAO_FRONTEND_DIR: frontendPath,
      DOUSHABAO_DATA_DIR: app.getPath("userData"),
      DOUSHABAO_DESKTOP: "1",
    };

    let proc;
    if (backendPath && fs.existsSync(backendPath)) {
      console.log(`[desktop] Starting bundled backend: ${backendPath}`);
      proc = spawn(backendPath, [], {
        env,
        cwd: path.dirname(backendPath),
        stdio: ["ignore", "pipe", "pipe"],
      });
    } else if (DEV_MODE) {
      // Development: run via uv
      const apiDir = path.join(__dirname, "..", "apps", "api");
      console.log(`[desktop] Dev mode: uv run uvicorn (cwd=${apiDir})`);
      proc = spawn(
        "uv",
        ["run", "uvicorn", "src.main:app", "--host", BACKEND_HOST, "--port", String(port)],
        { cwd: apiDir, env, stdio: ["ignore", "pipe", "pipe"] },
      );
    } else {
      reject(new Error("找不到后端可执行文件"));
      return;
    }

    backendProcess = proc;
    let stderrBuf = "";
    let settled = false;
    const finish = (err) => {
      if (settled) return;
      settled = true;
      if (err) reject(err);
      else resolve(port);
    };

    proc.stdout.on("data", (d) => process.stdout.write(`[backend] ${d}`));
    proc.stderr.on("data", (d) => {
      stderrBuf += d.toString();
      process.stderr.write(`[backend] ${d}`);
    });
    proc.on("error", (err) => {
      finish(new Error(`启动后端进程失败: ${err.message}\n${stderrBuf}`));
    });
    proc.on("exit", (code, signal) => {
      console.log(`[backend] exited code=${code} signal=${signal}`);
      backendProcess = null;
      if (code !== 0 && !settled) {
        finish(new Error(`后端进程异常退出 (code=${code})\n${stderrBuf}`));
      }
    });

    waitForServer(port, SERVER_READY_TIMEOUT).then(
      () => finish(),
      (err) => finish(err),
    );
  });
}

function stopBackend() {
  if (backendProcess) {
    try {
      if (process.platform === "win32") {
        spawn("taskkill", ["/pid", String(backendProcess.pid), "/f", "/t"]);
      } else {
        backendProcess.kill("SIGTERM");
        setTimeout(() => {
          if (backendProcess) backendProcess.kill("SIGKILL");
        }, 3000);
      }
    } catch {
      // ignore
    }
    backendProcess = null;
  }
}

// ═════════════════════════════════════════════════════════════════
//  Window management
// ═════════════════════════════════════════════════════════════════

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 920,
    minHeight: 640,
    title: "Doushabao",
    frame: IS_MAC,               // macOS: keep native frame for traffic lights; Win/Linux: frameless
    titleBarStyle: IS_MAC ? "hidden" : "default",
    trafficLightPosition: { x: 14, y: 12 },
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
    },
    show: false,
  });

  mainWindow.loadURL(`http://${BACKEND_HOST}:${actualPort}`);

  // Show window when ready to avoid flash
  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
    if (DEV_MODE) mainWindow.webContents.openDevTools();
  });

  // Forward maximize/unmaximize to renderer (for toggle button icon)
  mainWindow.on("maximize", () => {
    mainWindow.webContents.send("window-maximized-changed", true);
  });
  mainWindow.on("unmaximize", () => {
    mainWindow.webContents.send("window-maximized-changed", false);
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// ═════════════════════════════════════════════════════════════════
//  IPC handlers
// ═════════════════════════════════════════════════════════════════

const userDataPath = app.getPath("userData");
const configPath = path.join(userDataPath, "config.json");

function readConfig() {
  try {
    return JSON.parse(fs.readFileSync(configPath, "utf-8"));
  } catch {
    return {};
  }
}

function writeConfig(data) {
  fs.mkdirSync(path.dirname(configPath), { recursive: true });
  fs.writeFileSync(configPath, JSON.stringify(data, null, 2), "utf-8");
}

ipcMain.handle("get-app-info", () => ({
  version: app.getVersion(),
  platform: process.platform,
  arch: process.arch,
  userData: userDataPath,
}));

ipcMain.handle("open-external", (_event, url) => {
  shell.openExternal(url);
});

ipcMain.handle("get-config", (_event, key) => {
  const cfg = readConfig();
  return key ? cfg[key] : cfg;
});

ipcMain.handle("set-config", (_event, key, value) => {
  const cfg = readConfig();
  cfg[key] = value;
  writeConfig(cfg);
});

// ── Window control IPC (custom title bar) ─────────────────────

ipcMain.handle("window-minimize", () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.handle("window-maximize", () => {
  if (mainWindow) {
    mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize();
  }
});

ipcMain.handle("window-close", () => {
  if (mainWindow) mainWindow.close();
});

ipcMain.handle("window-is-maximized", () => {
  return mainWindow ? mainWindow.isMaximized() : false;
});

ipcMain.handle("window-is-maximizable", () => {
  return mainWindow ? mainWindow.isMaximizable() : false;
});

// ═════════════════════════════════════════════════════════════════
//  App lifecycle
// ═════════════════════════════════════════════════════════════════

app.whenReady().then(async () => {
  try {
    actualPort = await findAvailablePort(BACKEND_PORT_START);
    console.log(`[desktop] Starting backend on 127.0.0.1:${actualPort}`);
    await startBackend(actualPort);
    console.log("[desktop] Backend ready, creating window…");
    createWindow();
  } catch (err) {
    console.error("[desktop] Startup failed:", err);
    dialog.showErrorBox(
      "启动失败",
      `无法启动 Doushabao 服务。\n\n${err.message}\n\n请检查是否有其他实例正在运行。`,
    );
    app.quit();
  }
});

// macOS: re-create window when dock icon clicked
app.on("activate", () => {
  if (mainWindow === null) {
    app.whenReady().then(() => createWindow());
  }
});

app.on("window-all-closed", () => {
  stopBackend();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  stopBackend();
});

// Single-instance: focus existing window
app.on("second-instance", () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

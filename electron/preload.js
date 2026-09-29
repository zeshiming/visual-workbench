const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  /** Get app version & platform info. */
  getAppInfo: () =>
    ipcRenderer.invoke("get-app-info"),

  /** Open a URL in the system browser (external links). */
  openExternal: (url) =>
    ipcRenderer.invoke("open-external", url),

  /** Read/write user-level config (e.g. API keys). */
  getConfig: (key) =>
    ipcRenderer.invoke("get-config", key),
  setConfig: (key, value) =>
    ipcRenderer.invoke("set-config", key, value),

  /** Window controls (custom title bar). */
  minimizeWindow: () =>
    ipcRenderer.invoke("window-minimize"),
  maximizeWindow: () =>
    ipcRenderer.invoke("window-maximize"),
  closeWindow: () =>
    ipcRenderer.invoke("window-close"),
  isMaximized: () =>
    ipcRenderer.invoke("window-is-maximized"),
  isMaximizable: () =>
    ipcRenderer.invoke("window-is-maximizable"),

  /** Listen for maximize state changes. */
  onMaximizedChanged: (callback) =>
    ipcRenderer.on("window-maximized-changed", (_event, isMaximized) => callback(isMaximized)),

  /** Listen for backend messages. */
  onBackendLog: (callback) =>
    ipcRenderer.on("backend-log", (_event, msg) => callback(msg)),
});

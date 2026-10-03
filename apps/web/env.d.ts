/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

interface ElectronAPI {
  getAppInfo: () => Promise<{
    version: string
    platform: string
    arch: string
    userData: string
  }>
  openExternal: (url: string) => Promise<void>
  getConfig: (key?: string) => Promise<unknown>
  setConfig: (key: string, value: unknown) => Promise<void>
  minimizeWindow: () => Promise<void>
  maximizeWindow: () => Promise<void>
  closeWindow: () => Promise<void>
  isMaximized: () => Promise<boolean>
  isMaximizable: () => Promise<boolean>
  onMaximizedChanged: (callback: (isMaximized: boolean) => void) => void
  onBackendLog: (callback: (msg: string) => void) => void
}

interface Window {
  electronAPI?: ElectronAPI
}

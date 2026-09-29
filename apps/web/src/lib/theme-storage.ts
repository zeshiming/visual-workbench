import { loadBackendSettings, saveBackendSettings } from '@/lib/api-client'

export type Theme = 'light' | 'dark'

// The editing workspace is designed around a low-distraction dark canvas.
// Users can still switch to light mode from Settings, and an existing saved
// preference continues to take precedence over this first-run default.
export const DEFAULT_THEME: Theme = 'dark'

const STORAGE_KEY = 'visual-workbench-theme'
const LEGACY_STORAGE_KEY = 'doushabao-theme'

let currentTheme: Theme = DEFAULT_THEME

export function isTheme(value: unknown): value is Theme {
  return value === 'light' || value === 'dark'
}

function loadFromLocalStorage(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (isTheme(stored)) return stored

    // Keep an explicitly chosen dark preference from the old shell, but do
    // not carry its light default into the redesigned dark-first workspace.
    if (localStorage.getItem(LEGACY_STORAGE_KEY) === 'dark') return 'dark'
  } catch {
    // localStorage unavailable
  }
  return DEFAULT_THEME
}

function saveToLocalStorage(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // localStorage unavailable
  }
}

export function loadTheme(): Theme {
  currentTheme = loadFromLocalStorage()
  return currentTheme
}

export function saveTheme(theme: Theme): void {
  currentTheme = theme
  saveToLocalStorage(theme)
  saveBackendSettings({ theme }).catch(() => {
    // Backend unavailable — local storage already saved
  })
}

export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle('dark', theme === 'dark')
}

export async function syncThemeFromBackend(): Promise<Theme> {
  try {
    const settings = await loadBackendSettings()
    if (isTheme(settings.theme)) {
      currentTheme = settings.theme as Theme
      saveToLocalStorage(currentTheme)
      applyTheme(currentTheme)
      return currentTheme
    }
  } catch {
    // Backend unavailable — local storage already loaded
  }
  return currentTheme
}

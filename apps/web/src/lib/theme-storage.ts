import { loadBackendSettings, saveBackendSettings } from '@/lib/api-client'

export type Theme = 'light' | 'dark'

export const DEFAULT_THEME: Theme = 'light'

const STORAGE_KEY = 'doushabao-theme'

let currentTheme: Theme = DEFAULT_THEME

export function isTheme(value: unknown): value is Theme {
  return value === 'light' || value === 'dark'
}

function loadFromLocalStorage(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (isTheme(stored)) return stored
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

import {
  createId,
  emptyAppSettings,
  normalizeAppSettings,
  resolveRunConfig,
  validateAndResolveDefaults,
} from '@/lib/app-settings'
import { translate } from '@/i18n'
import { DEFAULT_OPENROUTER_HOST } from '@/lib/model-providers'
import { loadBackendSettings, saveBackendSettings } from '@/lib/api-client'
import { isTheme, applyTheme, saveTheme, type Theme } from '@/lib/theme-storage'
import { isAppLocale, saveLocale, type AppLocale } from '@/lib/locale-storage'
import { applyLocale } from '@/i18n'
import type { AppSettings, ModelEntry } from '@/types/app-settings'

export { DEFAULT_OPENROUTER_HOST }

type LegacyFlatConfig = {
  host?: string
  key?: string
  analysisModel?: string
  editModel?: string
  model?: string
}

type StoredPayload = Partial<AppSettings> & LegacyFlatConfig & {
  version?: number
}

function isAppSettings(parsed: StoredPayload): parsed is AppSettings {
  return Array.isArray(parsed.providers) && Array.isArray(parsed.models)
}

// ── In-memory cache ───────────────────────────────────────────

let cachedSettings: AppSettings | null = null

/**
 * Initialize the cache from the backend. Called once on app startup.
 * Also syncs theme and locale to in-memory stores.
 * Falls back to empty settings if backend is unavailable.
 */
export async function initAppSettings(): Promise<AppSettings> {
  let appSettings: AppSettings | null = null

  try {
    const backend = await loadBackendSettings()
    const raw = backend.app_settings

    // Sync theme to in-memory
    if (isTheme(backend.theme)) {
      saveTheme(backend.theme as Theme)
    }

    // Sync locale to in-memory
    if (isAppLocale(backend.locale)) {
      saveLocale(backend.locale as AppLocale)
      applyLocale(backend.locale as AppLocale)
    }

    if (raw && raw !== '{}') {
      const parsed = JSON.parse(raw) as StoredPayload
      if (isAppSettings(parsed)) {
        appSettings = normalizeAppSettings({
          providers: parsed.providers,
          models: parsed.models,
          defaultAnalysisModelId: parsed.defaultAnalysisModelId ?? '',
          defaultEditModelId: parsed.defaultEditModelId ?? '',
        })
      }
    }
  } catch {
    // Backend unavailable
  }

  cachedSettings = appSettings ?? emptyAppSettings()
  return cachedSettings
}

/**
 * Synchronous read from cache. Returns empty defaults if not yet initialized.
 */
export function loadAppSettings(): AppSettings {
  return cachedSettings ?? emptyAppSettings()
}

/**
 * Validate & persist settings to backend + update cache.
 */
export async function saveAppSettings(settings: AppSettings): Promise<AppSettings> {
  const validated = validateAndResolveDefaults(settings)
  cachedSettings = validated
  await saveBackendSettings({ app_settings: JSON.stringify(validated) }).catch(() => {
    // Backend unavailable — cache is still updated
  })
  return validated
}

/**
 * Clear all settings (reset to defaults in backend + cache).
 */
export async function clearAppSettings(): Promise<AppSettings> {
  try {
    await saveBackendSettings({ app_settings: "{}" })
  } catch {
    // Backend unavailable
  }

  cachedSettings = emptyAppSettings()
  return cachedSettings
}

export { resolveRunConfig } from '@/lib/app-settings'

import { loadBackendSettings, saveBackendSettings } from '@/lib/api-client'

export type AppLocale = 'zh-CN' | 'zh-Hant' | 'en' | 'ja' | 'ko'

export const FALLBACK_LOCALE: AppLocale = 'en'

export const SUPPORTED_LOCALES: AppLocale[] = ['zh-CN', 'zh-Hant', 'en', 'ja', 'ko']

let currentLocale: AppLocale | null = null

export function isAppLocale(value: unknown): value is AppLocale {
  return typeof value === 'string' && (SUPPORTED_LOCALES as string[]).includes(value)
}

function detectBrowserLocale(): AppLocale {
  const languages = navigator.languages?.length ? navigator.languages : [navigator.language]

  for (const language of languages) {
    const normalized = language.toLowerCase()

    if (
      normalized.startsWith('zh-hant') ||
      normalized.startsWith('zh-tw') ||
      normalized.startsWith('zh-hk') ||
      normalized.startsWith('zh-mo')
    ) {
      return 'zh-Hant'
    }

    if (normalized.startsWith('zh')) {
      return 'zh-CN'
    }

    if (normalized.startsWith('ja')) {
      return 'ja'
    }

    if (normalized.startsWith('ko')) {
      return 'ko'
    }

    if (normalized.startsWith('en')) {
      return 'en'
    }
  }

  return 'zh-CN'
}

export function loadLocale(): AppLocale {
  if (currentLocale) {
    return currentLocale
  }
  return detectBrowserLocale()
}

export function saveLocale(locale: AppLocale): void {
  currentLocale = locale
  saveBackendSettings({ locale }).catch(() => {
    // Backend unavailable
  })
}

export async function syncLocaleFromBackend(): Promise<AppLocale> {
  try {
    const settings = await loadBackendSettings()
    if (isAppLocale(settings.locale)) {
      currentLocale = settings.locale as AppLocale
      return currentLocale
    }
  } catch {
    // Backend unavailable
  }
  return loadLocale()
}

import { createI18n } from 'vue-i18n'
import type { WritableComputedRef } from 'vue'

import {
  FALLBACK_LOCALE,
  loadLocale,
  saveLocale,
  type AppLocale,
} from '@/lib/locale-storage'

import en from './locales/en'
import ja from './locales/ja'
import ko from './locales/ko'
import zhCN from './locales/zh-CN'
import zhHant from './locales/zh-Hant'
import type { MessageSchema } from './locales/en'

export const i18n = createI18n<[MessageSchema], AppLocale>({
  legacy: false,
  locale: loadLocale(),
  fallbackLocale: FALLBACK_LOCALE,
  messages: {
    en,
    'zh-CN': zhCN,
    'zh-Hant': zhHant,
    ja,
    ko,
  },
})

export function applyLocale(locale: AppLocale): void {
  ;(i18n.global.locale as unknown as WritableComputedRef<AppLocale>).value = locale
  document.documentElement.lang = locale
}

export function setLocale(locale: AppLocale): void {
  saveLocale(locale)
  applyLocale(locale)
}

export function translate(
  key: string,
  values?: Record<string, unknown>,
): string {
  return i18n.global.t(key, values ?? {})
}

export type { AppLocale, MessageSchema }

export { SUPPORTED_LOCALES } from '@/lib/locale-storage'

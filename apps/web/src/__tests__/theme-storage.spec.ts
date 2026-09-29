import { beforeEach, describe, expect, it } from 'vitest'

import {
  DEFAULT_THEME,
  applyTheme,
  loadTheme,
  saveTheme,
} from '../lib/theme-storage'

describe('theme-storage', () => {
  beforeEach(() => {
    document.documentElement.classList.remove('dark')
  })

  it('returns default theme when no theme has been set', () => {
    const saved = loadTheme()
    // After init, we use default
    expect(saved).toBe(DEFAULT_THEME)
  })

  it('saves and loads theme', () => {
    saveTheme('dark')
    expect(loadTheme()).toBe('dark')

    saveTheme('light')
    expect(loadTheme()).toBe('light')
  })

  it('applies dark class to document root', () => {
    applyTheme('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)

    applyTheme('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })
})

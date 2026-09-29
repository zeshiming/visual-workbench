import { describe, it, expect, beforeEach, vi } from 'vitest'

import { initAppSettings, loadAppSettings, saveAppSettings } from '../lib/config-storage'
import { resolveRunConfig } from '../lib/app-settings'
import { DEFAULT_GEMINI_HOST, DEFAULT_OPENROUTER_HOST } from '../lib/model-providers'
import type { AppSettings } from '../types/app-settings'

// Mock API client to avoid real HTTP calls
vi.mock('../lib/api-client', () => ({
  loadBackendSettings: vi.fn().mockRejectedValue(new Error('API unavailable')),
  saveBackendSettings: vi.fn().mockResolvedValue(undefined),
  clearBackendSettings: vi.fn().mockResolvedValue(undefined),
}))

function sampleSettings(): AppSettings {
  return {
    providers: [
      {
        id: 'openrouter' as const,
        host: 'https://openrouter.ai/api/v1',
        key: 'test-key',
      },
      {
        id: 'gemini' as const,
        host: DEFAULT_GEMINI_HOST,
        key: '',
      },
      {
        id: 'openai-compatible' as const,
        host: 'https://api.openai.com/v1',
        key: '',
      },
    ],
    models: [
      {
        id: 'analysis-1',
        providerId: 'openrouter' as const,
        modelId: 'google/gemini-2.5-flash-preview',
        label: '分析',
        roles: ['analysis' as const],
      },
      {
        id: 'edit-1',
        providerId: 'openrouter' as const,
        modelId: 'google/gemini-2.5-flash-image-preview',
        label: '修图',
        roles: ['edit' as const],
      },
    ],
    defaultAnalysisModelId: 'analysis-1',
    defaultEditModelId: 'edit-1',
  }
}

describe('config-storage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns three fixed providers from empty defaults', async () => {
    await initAppSettings()
    const settings = loadAppSettings()

    expect(settings.providers).toHaveLength(3)
    expect(settings.providers.map((provider) => provider.id)).toEqual([
      'openrouter',
      'gemini',
      'openai-compatible',
    ])
    expect(settings.providers[0]?.host).toBe(DEFAULT_OPENROUTER_HOST)
    expect(settings.models).toEqual([])
  })

  it('saves and loads validated settings', async () => {
    await initAppSettings()
    const settings = sampleSettings()

    await saveAppSettings(settings)

    expect(loadAppSettings()).toEqual(settings)
  })

  it('resolves runtime config from settings', async () => {
    await initAppSettings()
    const settings = sampleSettings()
    await saveAppSettings(settings)

    expect(resolveRunConfig(loadAppSettings())).toEqual({
      analysis: {
        host: 'https://openrouter.ai/api/v1',
        key: 'test-key',
        model: 'google/gemini-2.5-flash-preview',
      },
      edit: {
        host: 'https://openrouter.ai/api/v1',
        key: 'test-key',
        model: 'google/gemini-2.5-flash-image-preview',
      },
    })
  })

  it('rejects invalid settings', async () => {
    await initAppSettings()
    await expect(saveAppSettings(loadAppSettings())).rejects.toThrow()
  })
})

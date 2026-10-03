import { beforeEach, describe, expect, it, vi } from 'vitest'

import { runWorkspaceAgent } from '../lib/run-workspace-agent'
import type { Workspace } from '@/types/workspace'

vi.mock('../lib/api-client', async () => {
  const runAgentViaBackend = vi.fn()
  return { runAgentViaBackend }
})

vi.mock('../lib/config-storage', () => ({
  loadAppSettings: vi.fn(() => ({
    providers: [
      { id: 'openrouter', host: 'https://openrouter.ai/api/v1', key: 'test-key' },
      { id: 'gemini', host: 'https://generativelanguage.googleapis.com/v1beta/openai/', key: '' },
      { id: 'openai-compatible', host: 'https://api.openai.com/v1', key: '' },
    ],
    models: [
      {
        id: 'analysis-1',
        providerId: 'openrouter',
        modelId: 'analysis-model',
        label: '分析',
        roles: ['analysis'],
      },
      {
        id: 'edit-1',
        providerId: 'openrouter',
        modelId: 'edit-model',
        label: '修图',
        roles: ['edit'],
      },
    ],
    defaultAnalysisModelId: 'analysis-1',
    defaultEditModelId: 'edit-1',
  })),
}))

vi.mock('../lib/workspace-storage', () => ({
  hydrateWorkspaceImage: vi.fn(async (workspace: Workspace) => workspace),
}))

import { runAgentViaBackend } from '../lib/api-client'

const mockedRunAgentViaBackend = vi.mocked(runAgentViaBackend)

describe('run-workspace-agent', () => {
  const workspace: Workspace = {
    id: 'workspace-1',
    title: '测试',
    createdAt: 1,
    updatedAt: 1,
    sourceImage: 'data:image/png;base64,abc',
    hasSourceImage: true,
  }

  beforeEach(() => {
    mockedRunAgentViaBackend.mockReset()
  })

  it('calls runAgentViaBackend with hydrated workspace image', async () => {
    mockedRunAgentViaBackend.mockResolvedValue({
      analysis: {
        imageType: 'pure_portrait',
        imageTypeReason: '人物占满画面',
        deficiencies: [],
        summary: '良好',
        editPrompt: '轻微提亮肤色并增强眼部细节。',
      },
      analysisRaw: '{}',
      images: ['data:image/png;base64,result'],
      text: null,
    })

    await runWorkspaceAgent(workspace, '提高清晰度')

    expect(mockedRunAgentViaBackend).toHaveBeenCalledWith(
      {
        analysis: {
          host: 'https://openrouter.ai/api/v1',
          key: 'test-key',
          model: 'analysis-model',
        },
        edit: {
          host: 'https://openrouter.ai/api/v1',
          key: 'test-key',
          model: 'edit-model',
        },
      },
      'data:image/png;base64,abc',
      '提高清晰度',
      { onProgress: undefined },
    )
  })

  it('rejects when settings cannot resolve config', async () => {
    const { loadAppSettings } = await import('../lib/config-storage')
    vi.mocked(loadAppSettings).mockReturnValueOnce({
      providers: [],
      models: [],
      defaultAnalysisModelId: '',
      defaultEditModelId: '',
    })

    await expect(runWorkspaceAgent(workspace, '')).rejects.toThrow(
      '请先在设置中配置默认模型',
    )
  })
})

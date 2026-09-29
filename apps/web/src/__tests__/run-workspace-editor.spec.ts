import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createDraftWorkspace, getWorkspace, stageWorkspaceChanges } from '../lib/workspace-session'
import { runWorkspaceEditor } from '../lib/run-workspace-editor'

vi.mock('../lib/api-client', async () => {
  const generateImageViaBackend = vi.fn()
  return { generateImageViaBackend }
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

import { generateImageViaBackend } from '../lib/api-client'

const mockedGenerateImage = vi.mocked(generateImageViaBackend)

function stageWorkspaceWithImage(workspaceId: string) {
  stageWorkspaceChanges({
    id: workspaceId,
    title: '未命名工作区',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    sourceImage: 'data:image/png;base64,abc',
    hasSourceImage: true,
  })
}

describe('runWorkspaceEditor', () => {
  beforeEach(() => {
    mockedGenerateImage.mockReset()
  })

  it('requires at least one mark', async () => {
    createDraftWorkspace('workspace-1')
    stageWorkspaceWithImage('workspace-1')

    await expect(runWorkspaceEditor(getWorkspace('workspace-1')!, [])).rejects.toThrow(
      '请先在图片上圈选至少一个区域',
    )
  })

  it('sends marks to backend (no pre-built prompt)', async () => {
    createDraftWorkspace('workspace-1')
    stageWorkspaceWithImage('workspace-1')

    mockedGenerateImage.mockResolvedValue({
      images: ['data:image/png;base64,result'],
      text: null,
    })

    const result = await runWorkspaceEditor(getWorkspace('workspace-1')!, [
      {
        id: 'mark-1',
        centerX: 0.5,
        centerY: 0.5,
        radius: 0.1,
        description: '去掉杂物',
      },
    ])

    expect(result).toBe('data:image/png;base64,result')

    // Should call backend with image + marks (not pre-built prompt)
    const callArgs = mockedGenerateImage.mock.calls[0]!
    expect(callArgs[1]).toBe('data:image/png;base64,abc') // image
    expect(callArgs[2]).toEqual([
      expect.objectContaining({
        center_x: 0.5,
        center_y: 0.5,
        radius: 0.1,
        description: '去掉杂物',
      }),
    ])
  })
})

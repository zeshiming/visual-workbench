import { beforeEach, describe, expect, it, vi } from 'vitest'

import { exportImage } from '../lib/export-image'
import { canExportWorkspace, exportWorkspaceImage } from '../lib/export-workspace-image'
import { hydrateWorkspaceImage } from '../lib/workspace-storage'
import type { Workspace } from '../types/workspace'

vi.mock('../lib/export-image', () => ({
  exportImage: vi.fn(),
}))

vi.mock('../lib/workspace-storage', async (importOriginal) => {
  const original = await importOriginal<typeof import('../lib/workspace-storage')>()
  return {
    ...original,
    hydrateWorkspaceImage: vi.fn(),
  }
})

const mockedExportImage = vi.mocked(exportImage)
const mockedHydrateWorkspaceImage = vi.mocked(hydrateWorkspaceImage)

const workspace: Workspace = {
  id: 'workspace-1',
  title: '风景修图',
  createdAt: 1,
  updatedAt: 1,
  sourceImage: 'data:image/png;base64,abc',
  hasSourceImage: true,
}

describe('export-workspace-image', () => {
  beforeEach(() => {
    mockedExportImage.mockReset()
    mockedHydrateWorkspaceImage.mockReset()
  })

  it('returns true when workspace has image data', () => {
    expect(canExportWorkspace(workspace)).toBe(true)
    expect(canExportWorkspace({ ...workspace, sourceImage: undefined, hasSourceImage: true })).toBe(true)
    expect(canExportWorkspace(null)).toBe(false)
    expect(canExportWorkspace({ ...workspace, sourceImage: undefined, hasSourceImage: false })).toBe(false)
  })

  it('exports hydrated workspace image', async () => {
    mockedHydrateWorkspaceImage.mockResolvedValue(workspace)

    await exportWorkspaceImage(workspace)

    expect(mockedHydrateWorkspaceImage).toHaveBeenCalledWith(workspace)
    expect(mockedExportImage).toHaveBeenCalledWith('data:image/png;base64,abc', '风景修图')
  })

  it('throws when hydrated workspace has no image', async () => {
    mockedHydrateWorkspaceImage.mockResolvedValue({
      ...workspace,
      sourceImage: undefined,
      hasSourceImage: false,
    })

    await expect(exportWorkspaceImage(workspace)).rejects.toThrow('无法读取当前图片')
    expect(mockedExportImage).not.toHaveBeenCalled()
  })
})

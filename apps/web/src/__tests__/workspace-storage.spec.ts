import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  clearWorkspaceCache,
  DEFAULT_WORKSPACE_TITLE,
  createWorkspace,
  getRecentWorkspaces,
  hydrateWorkspaceImage,
  isPersistedWorkspace,
  isWorkspaceNameTaken,
  loadLastWorkspaceId,
  loadWorkspace,
  loadWorkspaces,
  replaceWorkspaceSourceImage,
  saveWorkspace,
} from '../lib/workspace-storage'
import { clearWorkspaceImages, loadWorkspaceImage } from '../lib/workspace-image-storage'

describe('workspace-storage', () => {
  beforeEach(() => {
    clearWorkspaceCache()
    clearWorkspaceImages()
  })

  it('returns empty map when no workspaces exist', () => {
    expect(loadWorkspaces()).toEqual({})
  })

  it('creates a workspace with an unnamed title', () => {
    const workspace = createWorkspace('workspace-1')

    expect(workspace.id).toBe('workspace-1')
    expect(workspace.title).toBe(DEFAULT_WORKSPACE_TITLE)
  })

  it('saves and loads a workspace', async () => {
    const workspace = createWorkspace('workspace-1')
    await saveWorkspace(workspace)

    const stored = loadWorkspace('workspace-1')
    expect(stored?.id).toBe('workspace-1')
    expect(stored?.title).toBe(DEFAULT_WORKSPACE_TITLE)
    expect(stored?.createdAt).toBe(workspace.createdAt)
    expect(stored?.updatedAt).toBeGreaterThanOrEqual(workspace.updatedAt)
    expect(loadLastWorkspaceId()).toBe('workspace-1')
  })

  it('detects persisted workspaces and duplicate names', async () => {
    expect(isPersistedWorkspace('workspace-1')).toBe(false)

    await saveWorkspace({
      ...createWorkspace('workspace-1'),
      title: '海报 A',
    })

    expect(isPersistedWorkspace('workspace-1')).toBe(true)
    expect(isWorkspaceNameTaken('海报 A')).toBe(true)
    expect(isWorkspaceNameTaken('海报 A', 'workspace-1')).toBe(false)
    expect(isWorkspaceNameTaken('海报 B')).toBe(false)
  })

  it('stores large source images via backend (or memory fallback)', async () => {
    const workspace = {
      ...createWorkspace('workspace-1'),
      title: '大图工作区',
      sourceImage: `data:image/png;base64,${'a'.repeat(1024 * 512)}`,
    }

    await saveWorkspace(workspace)

    // Workspace metadata should NOT contain the raw sourceImage
    expect(loadWorkspace('workspace-1')).toMatchObject({
      id: 'workspace-1',
      title: '大图工作区',
      hasSourceImage: true,
    })
    expect(loadWorkspace('workspace-1')?.sourceImage).toBeUndefined()

    // Image should be retrievable via hydrate
    const hydrated = await hydrateWorkspaceImage(loadWorkspace('workspace-1')!)
    expect(hydrated.sourceImage).toBe(workspace.sourceImage)
  })

  it('tracks the most recently updated workspace', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T00:00:00.000Z'))

    const first = createWorkspace('workspace-1')
    await saveWorkspace(first)

    vi.setSystemTime(new Date('2026-01-02T00:00:00.000Z'))
    const second = createWorkspace('workspace-2')
    await saveWorkspace(second)

    expect(getRecentWorkspaces().map((workspace) => workspace.id)).toEqual([
      'workspace-2',
      'workspace-1',
    ])
    expect(loadLastWorkspaceId()).toBe('workspace-2')

    vi.useRealTimers()
  })

  it('replaces stored source image', async () => {
    const workspace = {
      ...createWorkspace('workspace-1'),
      title: '测试项目',
      sourceImage: 'data:image/png;base64,original',
      hasSourceImage: true,
    }

    await saveWorkspace(workspace)

    const replaced = await replaceWorkspaceSourceImage(workspace, 'data:image/png;base64,edited')

    expect(replaced.sourceImage).toBe('data:image/png;base64,edited')
    expect(await loadWorkspaceImage('workspace-1')).toBe('data:image/png;base64,edited')
    expect(await hydrateWorkspaceImage(loadWorkspace('workspace-1')!)).toMatchObject({
      sourceImage: 'data:image/png;base64,edited',
    })
  })
})

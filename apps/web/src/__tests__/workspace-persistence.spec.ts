import { beforeEach, describe, expect, it, vi } from 'vitest'
import { saveWorkspace, loadWorkspace, clearWorkspaceCache, syncWorkspacesFromBackend } from '../lib/workspace-storage'
import { clearDraftWorkspaces, createDraftWorkspace, stageWorkspaceChanges, persistWorkspace, getWorkspace, isWorkspaceDirty } from '../lib/workspace-session'
import * as api from '../lib/api-client'

vi.mock('../lib/api-client', () => ({
  saveBackendWorkspaceImage: vi.fn(), commitBackendWorkspace: vi.fn(), deleteBackendWorkspaceImage: vi.fn(),
  getBackendWorkspaceImage: vi.fn(), createBackendWorkspace: vi.fn(),
  updateBackendWorkspace: vi.fn(), listBackendWorkspaces: vi.fn(),
  saveBackendSettings: vi.fn(), loadBackendSettings: vi.fn(), deleteBackendWorkspace: vi.fn(),
}))

beforeEach(() => {
  vi.resetAllMocks()
  clearWorkspaceCache()
  clearDraftWorkspaces()
  vi.mocked(api.listBackendWorkspaces).mockResolvedValue([])
  vi.mocked(api.saveBackendSettings).mockResolvedValue({} as never)
})

describe('durable workspace save', () => {
  it('serializes saves for one workspace and snapshots queued input', async () => {
    let finish!: () => void
    vi.mocked(api.commitBackendWorkspace).mockImplementationOnce(() => new Promise((resolve) => {
      finish = () => resolve(undefined as never)
    }))
    const base = { id: 'a', title: 'old', createdAt: 1, updatedAt: 1, sourceImage: 'old' }
    const first = saveWorkspace(base)
    const next = { ...base, title: 'new', sourceImage: 'new' }
    const second = saveWorkspace(next)
    next.sourceImage = 'not requested'
    expect(api.commitBackendWorkspace).toHaveBeenCalledTimes(1)
    finish()
    await Promise.all([first, second])
    expect(vi.mocked(api.commitBackendWorkspace).mock.calls.map((args) => args[1].image)).toEqual(['old', 'new'])
    expect(loadWorkspace('a')?.title).toBe('new')
  })

  it('allows the next queued save after a failure', async () => {
    vi.mocked(api.commitBackendWorkspace).mockRejectedValueOnce(new Error('offline'))
    const item = { id: 'a', title: 'a', createdAt: 1, updatedAt: 1, sourceImage: 'old' }
    const first = saveWorkspace(item)
    const second = saveWorkspace({ ...item, sourceImage: 'new' })
    await expect(first).rejects.toThrow('offline')
    await second
    expect(api.commitBackendWorkspace).toHaveBeenLastCalledWith('a', expect.objectContaining({ image: 'new' }))
    expect(loadWorkspace('a')).not.toBeNull()
  })
  it('preserves a save completed while startup settings are loading', async () => {
    vi.mocked(api.listBackendWorkspaces).mockResolvedValueOnce([
      { id: 'a', title: 'old', createdAt: 1, updatedAt: 1, hasSourceImage: false },
    ])
    let finish!: () => void
    vi.mocked(api.loadBackendSettings).mockReturnValue(new Promise((resolve) => { finish = () => resolve({} as never) }))
    const sync = syncWorkspacesFromBackend()
    await Promise.resolve()
    await saveWorkspace({ id: 'a', title: 'new', createdAt: 1, updatedAt: 2 })
    finish()
    await sync
    expect(loadWorkspace('a')?.title).toBe('new')
  })
  it('keeps dirty edits and reports image save failure', async () => {
    const item = { ...createDraftWorkspace('a'), sourceImage: 'data:image/png;base64,new' }
    stageWorkspaceChanges(item)
    vi.mocked(api.commitBackendWorkspace).mockRejectedValue(new Error('offline'))
    await expect(persistWorkspace(item)).rejects.toThrow('offline')
    expect(isWorkspaceDirty('a')).toBe(true)
    expect(getWorkspace('a')?.sourceImage).toBe(item.sourceImage)
    expect(loadWorkspace('a')).toBeNull()
  })

  it('does not delete unloaded image on metadata-only save', async () => {
    await saveWorkspace({ id: 'a', title: 'renamed', createdAt: 1, updatedAt: 1, hasSourceImage: true })
    expect(api.deleteBackendWorkspaceImage).not.toHaveBeenCalled()
    expect(api.commitBackendWorkspace).toHaveBeenCalledWith('a', expect.objectContaining({ title: 'renamed' }))
    expect(vi.mocked(api.commitBackendWorkspace).mock.calls[0]?.[1]).not.toHaveProperty('image')
    expect(loadWorkspace('a')?.hasSourceImage).toBe(true)
  })

  it('keeps edits made while a save is pending', async () => {
    const original = { ...createDraftWorkspace('a'), sourceImage: 'old' }
    stageWorkspaceChanges(original)
    let finish!: () => void
    vi.mocked(api.commitBackendWorkspace).mockReturnValue(new Promise((resolve) => { finish = () => resolve(undefined as never) }))
    const pending = persistWorkspace(original)
    stageWorkspaceChanges({ ...original, sourceImage: 'new' })
    finish()
    await pending
    expect(getWorkspace('a')?.sourceImage).toBe('new')
    expect(isWorkspaceDirty('a')).toBe(true)
  })

  it('does not publish metadata on backend failure', async () => {
    vi.mocked(api.commitBackendWorkspace).mockRejectedValue(new Error('disk full'))
    await expect(saveWorkspace({ id: 'a', title: 'a', createdAt: 1, updatedAt: 1 })).rejects.toThrow('disk full')
    expect(loadWorkspace('a')).toBeNull()
  })
})

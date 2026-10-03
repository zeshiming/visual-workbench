import { beforeEach, vi } from 'vitest'

// Stateful backend double: successful saves are acknowledged and readable.
vi.mock('../../lib/api-client', () => {
  const images = new Map<string, string>()
  const workspaces = new Map<string, Record<string, unknown>>()
  return {
    saveBackendWorkspaceImage: vi.fn(async (id: string, image: string) => { images.set(id, image) }),
    getBackendWorkspaceImage: vi.fn(async (id: string) => images.get(id)),
    deleteBackendWorkspaceImage: vi.fn(async (id: string) => { images.delete(id) }),
    listBackendWorkspaces: vi.fn(async () => [...workspaces.values()]),
    createBackendWorkspace: vi.fn(async (item: Record<string, unknown>) => { workspaces.set(item.id as string, item); return item }),
    updateBackendWorkspace: vi.fn(async (id: string, item: Record<string, unknown>) => { const next = { ...workspaces.get(id), ...item }; workspaces.set(id, next); return next }),
    commitBackendWorkspace: vi.fn(async (id: string, item: Record<string, unknown>) => {
      const next = { ...workspaces.get(id), id, ...item, hasSourceImage: 'image' in item ? item.image !== null : workspaces.get(id)?.hasSourceImage ?? false }
      workspaces.set(id, next)
      if ('image' in item && item.image !== null) images.set(id, item.image as string)
      if ('image' in item && item.image === null) images.delete(id)
      return next
    }),
    deleteBackendWorkspace: vi.fn(async (id: string) => { workspaces.delete(id) }),
    saveBackendSettings: vi.fn(async () => ({})),
    loadBackendSettings: vi.fn(async () => ({})),
    resetPersistenceDouble: () => { images.clear(); workspaces.clear() },
  }
})

beforeEach(async () => {
  const api = await import('../../lib/api-client') as unknown as { resetPersistenceDouble: () => void }
  api.resetPersistenceDouble()
})

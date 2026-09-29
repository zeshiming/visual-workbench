import {
  deleteBackendWorkspaceImage,
  getBackendWorkspaceImage,
  saveBackendWorkspaceImage,
} from '@/lib/api-client'

const memoryStore = new Map<string, string>()

/**
 * Save workspace image: primary to backend, fallback to in-memory.
 */
export async function saveWorkspaceImage(
  workspaceId: string,
  dataUrl: string | undefined,
): Promise<void> {
  if (!dataUrl) {
    // Delete from both
    await deleteBackendWorkspaceImage(workspaceId).catch(() => {})
    memoryStore.delete(workspaceId)
    return
  }

  // Try backend
  try {
    await saveBackendWorkspaceImage(workspaceId, dataUrl)
    return
  } catch {
    // Backend unavailable — fallback to in-memory
  }

  memoryStore.set(workspaceId, dataUrl)
}

/**
 * Load workspace image: try backend first, fallback to in-memory.
 */
export async function loadWorkspaceImage(workspaceId: string): Promise<string | undefined> {
  // Try backend
  try {
    const image = await getBackendWorkspaceImage(workspaceId)
    if (image) {
      return image
    }
  } catch {
    // Backend unavailable — fallback
  }

  return memoryStore.get(workspaceId)
}

/**
 * Delete workspace image from backend and memory.
 */
export async function deleteWorkspaceImage(workspaceId: string): Promise<void> {
  await saveWorkspaceImage(workspaceId, undefined)
}

export function clearWorkspaceImages(): void {
  memoryStore.clear()
}

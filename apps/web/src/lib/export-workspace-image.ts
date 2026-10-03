import { exportImage } from '@/lib/export-image'
import { hydrateWorkspaceImage } from '@/lib/workspace-storage'
import type { Workspace } from '@/types/workspace'

export function canExportWorkspace(workspace: Workspace | null | undefined): boolean {
  if (!workspace) {
    return false
  }

  return Boolean(workspace.sourceImage || workspace.hasSourceImage)
}

export async function exportWorkspaceImage(workspace: Workspace): Promise<void> {
  const hydrated = await hydrateWorkspaceImage(workspace)

  if (!hydrated.sourceImage) {
    throw new Error('无法读取当前图片')
  }

  await exportImage(hydrated.sourceImage, hydrated.title)
}

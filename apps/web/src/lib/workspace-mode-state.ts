import { ref } from 'vue'

import type { WorkspaceMode } from '@/types/workspace-mode'

export const workspaceMode = ref<WorkspaceMode>('photos')

export function setWorkspaceMode(mode: WorkspaceMode): void {
  workspaceMode.value = mode
}

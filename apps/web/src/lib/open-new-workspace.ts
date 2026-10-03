import type { Router } from 'vue-router'

import { createWorkspaceId } from '@/lib/workspace-id'
import { createDraftWorkspace, stageWorkspaceImageChange } from '@/lib/workspace-session'

export function openNewWorkspace(router: Router): void {
  const workspaceId = createWorkspaceId()
  createDraftWorkspace(workspaceId)

  void router.push({
    name: 'workspace',
    params: { workspaceId },
  })
}

export function openNewWorkspaceWithImage(router: Router, sourceImage: string): void {
  const workspaceId = createWorkspaceId()
  const workspace = createDraftWorkspace(workspaceId)

  stageWorkspaceImageChange({
    ...workspace,
    sourceImage,
    hasSourceImage: true,
  })

  void router.push({
    name: 'workspace',
    params: { workspaceId },
  })
}

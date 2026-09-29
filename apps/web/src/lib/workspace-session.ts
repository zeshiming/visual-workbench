import { computed, ref } from 'vue'

import type { Workspace } from '@/types/workspace'

import {
  DEFAULT_WORKSPACE_TITLE,
  createWorkspace,
  deleteWorkspace,
  loadWorkspace,
  saveWorkspace,
} from '@/lib/workspace-storage'
import { loadWorkspaceImage } from '@/lib/workspace-image-storage'
import {
  clearAllWorkspaceImageHistory,
  clearWorkspaceImageHistory,
  popWorkspaceImageUndo,
  recordWorkspaceImageHistory,
} from '@/lib/workspace-image-history'
import { clearWorkspaceEditorMarks, clearWorkspaceUiState, removeWorkspaceUiState } from '@/lib/workspace-ui-state'

export { canUndoWorkspaceImage, recordWorkspaceImageHistory } from '@/lib/workspace-image-history'

export const SETTINGS_TAB_ID = 'settings'

const draftWorkspaces = new Map<string, Workspace>()
const openTabIds = ref<string[]>([])
export const dirtyWorkspaceIds = ref<Set<string>>(new Set())

export const openTabs = computed(() => openTabIds.value)

export function isSettingsTab(id: string): boolean {
  return id === SETTINGS_TAB_ID
}

export const openWorkspaces = computed(() =>
  openTabIds.value
    .filter((id) => !isSettingsTab(id))
    .map((id) => getWorkspace(id))
    .filter((workspace): workspace is Workspace => workspace !== null),
)

export function isWorkspaceDirty(id: string): boolean {
  return dirtyWorkspaceIds.value.has(id)
}

export function markWorkspaceDirty(id: string): void {
  if (dirtyWorkspaceIds.value.has(id)) {
    return
  }

  dirtyWorkspaceIds.value = new Set([...dirtyWorkspaceIds.value, id])
}

export function markWorkspaceClean(id: string): void {
  if (!dirtyWorkspaceIds.value.has(id)) {
    return
  }

  const next = new Set(dirtyWorkspaceIds.value)
  next.delete(id)
  dirtyWorkspaceIds.value = next
}

export function isDefaultWorkspace(workspace: Workspace): boolean {
  return workspace.title === DEFAULT_WORKSPACE_TITLE
}

export function createDraftWorkspace(id: string): Workspace {
  const workspace = createWorkspace(id)
  draftWorkspaces.set(id, workspace)
  addOpenWorkspace(id)
  return workspace
}

export function getWorkspace(id: string): Workspace | null {
  return draftWorkspaces.get(id) ?? loadWorkspace(id) ?? null
}

export function isDraftWorkspace(id: string): boolean {
  return draftWorkspaces.has(id)
}

export function updateDraftWorkspace(workspace: Workspace): void {
  if (draftWorkspaces.has(workspace.id)) {
    draftWorkspaces.set(workspace.id, workspace)
  }
}

export function stageWorkspaceChanges(workspace: Workspace): void {
  draftWorkspaces.set(workspace.id, workspace)
  markWorkspaceDirty(workspace.id)
  openTabIds.value = [...openTabIds.value]
  workspaceContentRevision.value += 1
}

export const workspaceImageRevisions = ref<Record<string, number>>({})
export const workspaceContentRevision = ref(0)
export const workspaceEditingIds = ref<Set<string>>(new Set())

export function getWorkspaceImageRevision(workspaceId: string): number {
  return workspaceImageRevisions.value[workspaceId] ?? 0
}

function bumpWorkspaceImageRevision(workspaceId: string): void {
  workspaceImageRevisions.value = {
    ...workspaceImageRevisions.value,
    [workspaceId]: getWorkspaceImageRevision(workspaceId) + 1,
  }
}

export function setWorkspaceEditing(workspaceId: string, editing: boolean): void {
  const next = new Set(workspaceEditingIds.value)

  if (editing) {
    next.add(workspaceId)
  } else {
    next.delete(workspaceId)
  }

  workspaceEditingIds.value = next
}

export function isWorkspaceEditing(workspaceId: string): boolean {
  return workspaceEditingIds.value.has(workspaceId)
}

export function stageWorkspaceImageChange(workspace: Workspace): void {
  stageWorkspaceChanges(workspace)
  clearWorkspaceEditorMarks(workspace.id)
  bumpWorkspaceImageRevision(workspace.id)
}

export async function applyWorkspaceGeneratedImage(
  workspace: Workspace,
  sourceImage: string,
): Promise<Workspace> {
  const previousImage = workspace.sourceImage ?? (await loadWorkspaceImage(workspace.id))
  if (previousImage && previousImage !== sourceImage) {
    recordWorkspaceImageHistory(workspace.id, previousImage)
  }

  const nextWorkspace: Workspace = {
    ...workspace,
    sourceImage,
    hasSourceImage: true,
    updatedAt: Date.now(),
  }

  stageWorkspaceChanges(nextWorkspace)
  clearWorkspaceEditorMarks(workspace.id)

  return nextWorkspace
}

export async function undoWorkspaceImageChange(workspaceId: string): Promise<Workspace | null> {
  const workspace = getWorkspace(workspaceId)
  const previousImage = popWorkspaceImageUndo(workspaceId)

  if (!workspace || !previousImage) {
    return null
  }

  const nextWorkspace: Workspace = {
    ...workspace,
    sourceImage: previousImage,
    hasSourceImage: true,
    updatedAt: Date.now(),
  }

  stageWorkspaceChanges(nextWorkspace)
  clearWorkspaceEditorMarks(workspaceId)
  bumpWorkspaceImageRevision(workspaceId)

  return nextWorkspace
}

/** @deprecated Use applyWorkspaceGeneratedImage */
export function stageWorkspaceGeneratedImage(workspace: Workspace, sourceImage: string): Workspace {
  const nextWorkspace: Workspace = {
    ...workspace,
    sourceImage,
    hasSourceImage: true,
    updatedAt: Date.now(),
  }

  stageWorkspaceChanges(nextWorkspace)
  return nextWorkspace
}

export function addOpenWorkspace(id: string): void {
  if (openTabIds.value.includes(id)) {
    return
  }

  clearWorkspaceImageHistory(id)
  openTabIds.value = [...openTabIds.value, id]
}

export function addSettingsTab(): void {
  if (openTabIds.value.includes(SETTINGS_TAB_ID)) {
    return
  }

  openTabIds.value = [...openTabIds.value, SETTINGS_TAB_ID]
}

export function removeOpenTab(id: string): void {
  openTabIds.value = openTabIds.value.filter((openId) => openId !== id)
}

export function removeOpenWorkspace(id: string): void {
  removeOpenTab(id)
}

export async function persistWorkspace(workspace: Workspace): Promise<void> {
  await saveWorkspace(workspace)
  draftWorkspaces.delete(workspace.id)
  markWorkspaceClean(workspace.id)
  openTabIds.value = [...openTabIds.value]
  workspaceContentRevision.value += 1
}

export function discardWorkspace(id: string): void {
  draftWorkspaces.delete(id)
}

export function deleteSavedWorkspace(id: string): void {
  draftWorkspaces.delete(id)
  void deleteWorkspace(id)
}

export async function removeSavedProject(id: string): Promise<string | null> {
  const index = openTabIds.value.indexOf(id)
  const nextTabId = index >= 0 ? getNextTabIdAfterClose(index) : null

  draftWorkspaces.delete(id)
  markWorkspaceClean(id)

  if (index >= 0) {
    removeOpenTab(id)
  }

  await deleteWorkspace(id)

  clearWorkspaceImageHistory(id)
  removeWorkspaceUiState(id)

  return nextTabId
}

function getNextTabIdAfterClose(index: number): string | null {
  if (index < 0) {
    return null
  }

  return openTabIds.value[index + 1] ?? openTabIds.value[index - 1] ?? null
}

export function closeTab(id: string): string | null {
  const index = openTabIds.value.indexOf(id)
  const nextId = getNextTabIdAfterClose(index)

  removeOpenTab(id)

  if (!isSettingsTab(id)) {
    discardWorkspace(id)
    markWorkspaceClean(id)
    clearWorkspaceImageHistory(id)
  }

  return nextId
}

export function closeWorkspaceTab(id: string): string | null {
  return closeTab(id)
}

export function clearDraftWorkspaces(): void {
  draftWorkspaces.clear()
  openTabIds.value = []
  dirtyWorkspaceIds.value = new Set()
  workspaceEditingIds.value = new Set()
  workspaceContentRevision.value = 0
  workspaceImageRevisions.value = {}
  clearAllWorkspaceImageHistory()
  clearWorkspaceUiState()
}

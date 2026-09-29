import { ref } from 'vue'

import type { AgentImageAnalysis } from '@/types/agent'

import type { EditMode } from '@/lib/edit-mode'
import type { EditorMark } from '@/types/editor-mark'
import type { BasicImageAdjustments } from '@/lib/image-adjustments'

export type WorkspaceRunStep = 'analysis' | 'edit'

type WorkspaceUiState = {
  editMode: EditMode
  editorMarks: EditorMark[]
  editorMarksRevision: number
  agentPrompt: string
  /** null = use settings default */
  selectedAnalysisModelId: string | null
  selectedEditModelId: string | null
  runStep: WorkspaceRunStep | null
  runError: string
  analysis: AgentImageAnalysis | null
  selectedAssetIds: string[]
  activeAssetId: string | null
  assetAdjustments: Record<string, BasicImageAdjustments>
}

const workspaceUiStates = new Map<string, WorkspaceUiState>()

export const workspaceUiRevision = ref(0)
export const workspaceAssetsRevision = ref(0)

function loadAssetAdjustments(workspaceId: string): Record<string, BasicImageAdjustments> {
  try {
    const stored = localStorage.getItem(`visual-workbench-adjustments:${workspaceId}`)
    if (stored) return JSON.parse(stored) as Record<string, BasicImageAdjustments>
  } catch {
    // Ignore malformed or unavailable local storage.
  }
  return {}
}

function createDefaultState(workspaceId: string): WorkspaceUiState {
  return {
    editMode: 'agent',
    editorMarks: [],
    editorMarksRevision: 0,
    agentPrompt: '',
    selectedAnalysisModelId: null,
    selectedEditModelId: null,
    runStep: null,
    runError: '',
    analysis: null,
    selectedAssetIds: [],
    activeAssetId: null,
    assetAdjustments: loadAssetAdjustments(workspaceId),
  }
}

function getState(workspaceId: string): WorkspaceUiState {
  let state = workspaceUiStates.get(workspaceId)

  if (!state) {
    state = createDefaultState(workspaceId)
    workspaceUiStates.set(workspaceId, state)
  }

  return state
}

function bumpRevision(): void {
  workspaceUiRevision.value += 1
}

export function getWorkspaceEditMode(workspaceId: string): EditMode {
  return getState(workspaceId).editMode
}

export function setWorkspaceEditMode(workspaceId: string, mode: EditMode): void {
  const state = getState(workspaceId)

  if (state.editMode === mode) {
    return
  }

  state.editMode = mode
  bumpRevision()
}

function bumpEditorMarksRevision(state: WorkspaceUiState): void {
  state.editorMarksRevision += 1
  bumpRevision()
}

export function getWorkspaceEditorMarks(workspaceId: string): EditorMark[] {
  return [...getState(workspaceId).editorMarks]
}

export function getWorkspaceEditorMarksRevision(workspaceId: string): number {
  return getState(workspaceId).editorMarksRevision
}

export function setWorkspaceEditorMarks(workspaceId: string, marks: EditorMark[]): void {
  getState(workspaceId).editorMarks = marks
  bumpRevision()
}

export function clearWorkspaceEditorMarks(workspaceId: string): void {
  const state = getState(workspaceId)

  if (state.editorMarks.length === 0) {
    return
  }

  state.editorMarks = []
  bumpEditorMarksRevision(state)
}

export function getWorkspaceAgentPrompt(workspaceId: string): string {
  return getState(workspaceId).agentPrompt
}

export function setWorkspaceAgentPrompt(workspaceId: string, prompt: string): void {
  const state = getState(workspaceId)

  if (state.agentPrompt === prompt) {
    return
  }

  state.agentPrompt = prompt
  bumpRevision()
}

export function getWorkspaceSelectedAnalysisModelId(workspaceId: string): string | null {
  return getState(workspaceId).selectedAnalysisModelId
}

export function setWorkspaceSelectedAnalysisModelId(
  workspaceId: string,
  modelId: string | null,
): void {
  const state = getState(workspaceId)

  if (state.selectedAnalysisModelId === modelId) {
    return
  }

  state.selectedAnalysisModelId = modelId
  bumpRevision()
}

export function getWorkspaceSelectedEditModelId(workspaceId: string): string | null {
  return getState(workspaceId).selectedEditModelId
}

export function setWorkspaceSelectedEditModelId(workspaceId: string, modelId: string | null): void {
  const state = getState(workspaceId)

  if (state.selectedEditModelId === modelId) {
    return
  }

  state.selectedEditModelId = modelId
  bumpRevision()
}

export function getWorkspaceModelSelection(workspaceId: string): {
  analysisModelId: string | null
  editModelId: string | null
} {
  const state = getState(workspaceId)

  return {
    analysisModelId: state.selectedAnalysisModelId,
    editModelId: state.selectedEditModelId,
  }
}

export function isWorkspaceRunning(workspaceId: string): boolean {
  return getState(workspaceId).runStep !== null
}

export function getWorkspaceRunStep(workspaceId: string): WorkspaceRunStep | null {
  return getState(workspaceId).runStep
}

export function setWorkspaceRunStep(workspaceId: string, step: WorkspaceRunStep | null): void {
  getState(workspaceId).runStep = step
  bumpRevision()
}

export function getWorkspaceRunError(workspaceId: string): string {
  return getState(workspaceId).runError
}

export function setWorkspaceRunError(workspaceId: string, error: string): void {
  getState(workspaceId).runError = error
  bumpRevision()
}

export function getWorkspaceAnalysis(workspaceId: string): AgentImageAnalysis | null {
  return getState(workspaceId).analysis
}

export function setWorkspaceAnalysis(
  workspaceId: string,
  analysis: AgentImageAnalysis | null,
): void {
  getState(workspaceId).analysis = analysis
  bumpRevision()
}

export function clearWorkspaceRunPresentation(workspaceId: string): void {
  const state = getState(workspaceId)
  state.runError = ''
  state.analysis = null
  bumpRevision()
}

export function getWorkspaceSelectedAssetIds(workspaceId: string): string[] {
  return [...getState(workspaceId).selectedAssetIds]
}

export function setWorkspaceSelectedAssetIds(workspaceId: string, assetIds: string[]): void {
  const state = getState(workspaceId)
  const next = [...new Set(assetIds)]
  if (state.selectedAssetIds.join('|') === next.join('|')) return
  state.selectedAssetIds = next
  bumpRevision()
}

export function getWorkspaceActiveAssetId(workspaceId: string): string | null {
  return getState(workspaceId).activeAssetId
}

export function setWorkspaceActiveAssetId(workspaceId: string, assetId: string | null): void {
  const state = getState(workspaceId)
  if (state.activeAssetId === assetId) return
  state.activeAssetId = assetId
  bumpRevision()
}

export function getWorkspaceAssetAdjustments(
  workspaceId: string,
  assetId: string | null,
  fallback: BasicImageAdjustments,
): BasicImageAdjustments {
  if (!assetId) return { ...fallback }
  return { ...fallback, ...(getState(workspaceId).assetAdjustments[assetId] ?? {}) }
}

export function setWorkspaceAssetAdjustments(
  workspaceId: string,
  assetId: string | null,
  adjustments: BasicImageAdjustments,
): void {
  if (!assetId) return
  getState(workspaceId).assetAdjustments[assetId] = { ...adjustments }
  try {
    localStorage.setItem(
      `visual-workbench-adjustments:${workspaceId}`,
      JSON.stringify(getState(workspaceId).assetAdjustments),
    )
  } catch {
    // In-memory state remains usable when storage is unavailable.
  }
  bumpRevision()
}

export function notifyWorkspaceAssetsChanged(): void {
  workspaceAssetsRevision.value += 1
}

export function removeWorkspaceUiState(workspaceId: string): void {
  workspaceUiStates.delete(workspaceId)
  try {
    localStorage.removeItem(`visual-workbench-adjustments:${workspaceId}`)
  } catch {
    // Ignore unavailable local storage.
  }
}

export function clearWorkspaceUiState(): void {
  workspaceUiStates.clear()
  workspaceUiRevision.value = 0
  workspaceAssetsRevision.value = 0
}

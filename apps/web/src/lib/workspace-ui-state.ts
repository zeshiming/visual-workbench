import { ref } from 'vue'

import type { AgentImageAnalysis } from '@/types/agent'

import type { EditMode } from '@/lib/edit-mode'
import type { EditorMark } from '@/types/editor-mark'

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
}

const workspaceUiStates = new Map<string, WorkspaceUiState>()

export const workspaceUiRevision = ref(0)

function createDefaultState(): WorkspaceUiState {
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
  }
}

function getState(workspaceId: string): WorkspaceUiState {
  let state = workspaceUiStates.get(workspaceId)

  if (!state) {
    state = createDefaultState()
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

export function removeWorkspaceUiState(workspaceId: string): void {
  workspaceUiStates.delete(workspaceId)
}

export function clearWorkspaceUiState(): void {
  workspaceUiStates.clear()
  workspaceUiRevision.value = 0
}

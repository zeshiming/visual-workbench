import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearWorkspaceUiState,
  getWorkspaceAgentPrompt,
  getWorkspaceEditMode,
  getWorkspaceEditorMarks,
  getWorkspaceRunStep,
  isWorkspaceRunning,
  setWorkspaceAgentPrompt,
  setWorkspaceEditMode,
  setWorkspaceEditorMarks,
  setWorkspaceRunStep,
} from '../lib/workspace-ui-state'

describe('workspace-ui-state', () => {
  beforeEach(() => {
    clearWorkspaceUiState()
  })

  it('keeps edit mode per workspace', () => {
    setWorkspaceEditMode('workspace-a', 'editor')
    setWorkspaceEditMode('workspace-b', 'agent')

    expect(getWorkspaceEditMode('workspace-a')).toBe('editor')
    expect(getWorkspaceEditMode('workspace-b')).toBe('agent')
  })

  it('keeps editor marks and agent prompt per workspace', () => {
    setWorkspaceEditorMarks('workspace-a', [
      {
        id: 'mark-1',
        centerX: 0.5,
        centerY: 0.5,
        radius: 0.1,
        description: '提亮',
      },
    ])
    setWorkspaceAgentPrompt('workspace-a', '整体偏暗')

    expect(getWorkspaceEditorMarks('workspace-a')).toHaveLength(1)
    expect(getWorkspaceAgentPrompt('workspace-a')).toBe('整体偏暗')
    expect(getWorkspaceEditorMarks('workspace-b')).toEqual([])
  })

  it('tracks run state per workspace independently', () => {
    setWorkspaceRunStep('workspace-a', 'analysis')

    expect(isWorkspaceRunning('workspace-a')).toBe(true)
    expect(getWorkspaceRunStep('workspace-a')).toBe('analysis')
    expect(isWorkspaceRunning('workspace-b')).toBe(false)
  })
})

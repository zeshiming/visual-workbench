import { describe, expect, it } from 'vitest'

import {
  canUndoWorkspaceImage,
  clearWorkspaceImageHistory,
  popWorkspaceImageUndo,
  recordWorkspaceImageHistory,
} from '../lib/workspace-image-history'

describe('workspace-image-history', () => {
  it('tracks and restores previous images', () => {
    recordWorkspaceImageHistory('workspace-1', 'data:image/png;base64,original')
    recordWorkspaceImageHistory('workspace-1', 'data:image/png;base64,edited-once')

    expect(canUndoWorkspaceImage('workspace-1')).toBe(true)
    expect(popWorkspaceImageUndo('workspace-1')).toBe('data:image/png;base64,edited-once')
    expect(popWorkspaceImageUndo('workspace-1')).toBe('data:image/png;base64,original')
    expect(canUndoWorkspaceImage('workspace-1')).toBe(false)
  })

  it('clears history for a workspace', () => {
    recordWorkspaceImageHistory('workspace-1', 'data:image/png;base64,original')
    clearWorkspaceImageHistory('workspace-1')

    expect(canUndoWorkspaceImage('workspace-1')).toBe(false)
  })
})

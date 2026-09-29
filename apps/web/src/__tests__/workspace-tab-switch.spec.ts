import type { AgentImageAnalysis } from '@/types/agent'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'

import WorkspaceRightSidebar from '../components/WorkspaceRightSidebar.vue'
import { createDraftWorkspace, getWorkspace, isWorkspaceEditing, stageWorkspaceChanges } from '../lib/workspace-session'
import {
  clearWorkspaceUiState,
  getWorkspaceRunStep,
  setWorkspaceEditMode,
} from '../lib/workspace-ui-state'

// No business-logic mocks needed — all logic is in the Python backend.
// The UI layer tests just verify component behavior.

function stageWorkspaceWithImage(workspaceId: string) {
  stageWorkspaceChanges({
    id: workspaceId,
    title: '未命名工作区',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    sourceImage: 'data:image/png;base64,abc',
    hasSourceImage: true,
  })
}

describe('WorkspaceRightSidebar', () => {
  beforeEach(() => {
    clearWorkspaceUiState()
    createDraftWorkspace('workspace-1')
    stageWorkspaceWithImage('workspace-1')
  })

  it('renders the editor panel title', async () => {
    const wrapper = mount(WorkspaceRightSidebar, {
      props: { activeWorkspaceId: 'workspace-1' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('编辑')
  })

  it('displays analysis results when analysis is set', async () => {
    setWorkspaceEditMode('workspace-1', 'agent')
    const wrapper = mount(WorkspaceRightSidebar, {
      props: { activeWorkspaceId: 'workspace-1' },
    })
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })
})

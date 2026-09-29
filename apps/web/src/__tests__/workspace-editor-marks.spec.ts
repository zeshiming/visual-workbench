import { beforeEach, describe, expect, it, vi } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'

import WorkspaceRightSidebar from '../components/WorkspaceRightSidebar.vue'
import { createDraftWorkspace, stageWorkspaceChanges } from '../lib/workspace-session'
import {
  clearWorkspaceUiState,
  getWorkspaceEditorMarks,
  setWorkspaceEditMode,
  setWorkspaceEditorMarks,
} from '../lib/workspace-ui-state'

vi.mock('../lib/run-workspace-editor', () => ({
  runWorkspaceEditor: vi.fn(),
}))

import { runWorkspaceEditor } from '../lib/run-workspace-editor'

const mockedRunWorkspaceEditor = vi.mocked(runWorkspaceEditor)

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

function findEditorRunButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('button').find((button) => button.text().includes('开始修图'))
}

describe('WorkspaceRightSidebar editor marks', () => {
  beforeEach(() => {
    localStorage.clear()
    clearWorkspaceUiState()
    mockedRunWorkspaceEditor.mockReset()
  })

  it('clears editor marks after a successful editor run', async () => {
    createDraftWorkspace('workspace-1')
    stageWorkspaceWithImage('workspace-1')
    setWorkspaceEditMode('workspace-1', 'editor')
    setWorkspaceEditorMarks('workspace-1', [
      {
        id: 'mark-1',
        centerX: 0.5,
        centerY: 0.5,
        radius: 0.1,
        description: '去掉杂物',
      },
    ])

    mockedRunWorkspaceEditor.mockResolvedValue('data:image/png;base64,result')

    const wrapper = mount(WorkspaceRightSidebar, {
      props: {
        activeWorkspaceId: 'workspace-1',
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('1 号圈')

    await findEditorRunButton(wrapper)!.trigger('click')
    await flushPromises()

    expect(mockedRunWorkspaceEditor).toHaveBeenCalled()

    expect(getWorkspaceEditorMarks('workspace-1')).toEqual([])
    expect(wrapper.text()).not.toContain('1 号圈')
    expect(wrapper.text()).toContain('尚未圈选区域')
  })

  it('keeps editor marks when editor run fails', async () => {
    createDraftWorkspace('workspace-1')
    stageWorkspaceWithImage('workspace-1')
    setWorkspaceEditMode('workspace-1', 'editor')
    setWorkspaceEditorMarks('workspace-1', [
      {
        id: 'mark-1',
        centerX: 0.5,
        centerY: 0.5,
        radius: 0.1,
        description: '去掉杂物',
      },
    ])

    mockedRunWorkspaceEditor.mockRejectedValue(new Error('修图失败'))

    const wrapper = mount(WorkspaceRightSidebar, {
      props: {
        activeWorkspaceId: 'workspace-1',
      },
    })
    await flushPromises()

    await findEditorRunButton(wrapper)!.trigger('click')
    await flushPromises()

    expect(mockedRunWorkspaceEditor).toHaveBeenCalled()

    expect(getWorkspaceEditorMarks('workspace-1')).toHaveLength(1)
    expect(wrapper.text()).toContain('1 号圈')
  })
})

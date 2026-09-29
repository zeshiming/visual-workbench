import { beforeEach, describe, expect, it, vi } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'

import WorkspaceRightSidebar from '../components/WorkspaceRightSidebar.vue'
import { createDraftWorkspace, getWorkspace, stageWorkspaceChanges } from '../lib/workspace-session'
import { clearWorkspaceUiState } from '../lib/workspace-ui-state'

vi.mock('../lib/run-workspace-agent', () => ({
  runWorkspaceAgent: vi.fn(),
}))

import { runWorkspaceAgent } from '../lib/run-workspace-agent'

const mockedRunWorkspaceAgent = vi.mocked(runWorkspaceAgent)

function findActionButton(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('button').find((button) => button.text().includes(label))
}

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
    localStorage.clear()
    clearWorkspaceUiState()
    mockedRunWorkspaceAgent.mockReset()
  })

  it('shows hint when no workspace is active', async () => {
    const wrapper = mount(WorkspaceRightSidebar, {
      props: {
        activeWorkspaceId: '',
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('打开或新建工作区以开始编辑')
  })

  it('shows upload hint when workspace has no image', async () => {
    createDraftWorkspace('workspace-1')

    const wrapper = mount(WorkspaceRightSidebar, {
      props: {
        activeWorkspaceId: 'workspace-1',
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('请先上传图片')
  })

  it('shows agent form by default when workspace has an image', async () => {
    createDraftWorkspace('workspace-1')
    stageWorkspaceWithImage('workspace-1')

    const wrapper = mount(WorkspaceRightSidebar, {
      props: {
        activeWorkspaceId: 'workspace-1',
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Agent')
    expect(wrapper.text()).toContain('Editor')
    expect(wrapper.text()).toContain('修图需求（可选）')
    expect(wrapper.find('textarea').exists()).toBe(true)
    expect(wrapper.text()).toContain('开始 Agent')
  })

  it('allows agent run without prompt', async () => {
    createDraftWorkspace('workspace-1')
    stageWorkspaceWithImage('workspace-1')

    const wrapper = mount(WorkspaceRightSidebar, {
      props: {
        activeWorkspaceId: 'workspace-1',
      },
    })
    await flushPromises()

    expect(findActionButton(wrapper, '开始 Agent')?.attributes('disabled')).toBeUndefined()
  })

  it('shows editor annotation panel when editor mode is selected', async () => {
    createDraftWorkspace('workspace-1')
    stageWorkspaceWithImage('workspace-1')

    const wrapper = mount(WorkspaceRightSidebar, {
      props: {
        activeWorkspaceId: 'workspace-1',
      },
    })
    await flushPromises()

    const editorTab = wrapper.findAll('button[role="tab"]').find((button) => button.text() === 'Editor')
    await editorTab!.trigger('click')

    expect(wrapper.text()).toContain('在图片上拖拽画圈')
    expect(wrapper.text()).toContain('开始修图')
    expect(wrapper.text()).toContain('导出图片')
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  it('renders analysis result after agent run succeeds', async () => {
    createDraftWorkspace('workspace-1')
    stageWorkspaceWithImage('workspace-1')

    mockedRunWorkspaceAgent.mockResolvedValue({
      analysis: {
        imageType: 'landscape',
        imageTypeReason: '画面以自然山景为主',
        deficiencies: [
          {
            category: 'color',
            description: '整体偏灰，饱和度偏低',
            severity: 'medium',
          },
        ],
        summary: '构图良好，但色彩偏淡。',
        editPrompt: '提升整体饱和度，让天空与植被更鲜明，保持自然观感。',
      },
      analysisRaw: '{}',
      images: ['data:image/png;base64,result'],
      text: null,
    })

    const wrapper = mount(WorkspaceRightSidebar, {
      props: {
        activeWorkspaceId: 'workspace-1',
      },
    })
    await flushPromises()

    await findActionButton(wrapper, '开始 Agent')!.trigger('click')
    await flushPromises()

    expect(mockedRunWorkspaceAgent).toHaveBeenCalled()
    expect(wrapper.text()).toContain('分析结果')
    expect(wrapper.text()).toContain('风景')
    expect(wrapper.text()).toContain('色彩')
    expect(wrapper.text()).toContain('整体偏灰，饱和度偏低')
    expect(wrapper.text()).toContain('修图指令')
    expect(wrapper.text()).toContain('提升整体饱和度')
    expect(getWorkspace('workspace-1')?.sourceImage).toBe('data:image/png;base64,result')
  })
})

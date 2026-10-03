import { beforeEach, describe, expect, it, vi } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'

import WorkspaceRightSidebar from '../components/WorkspaceRightSidebar.vue'
import { createDraftWorkspace, getWorkspace, stageWorkspaceChanges } from '../lib/workspace-session'
import { clearWorkspaceUiState, setWorkspaceAgentPlan, setWorkspaceAgentPrompt, getWorkspaceAgentPlan } from '../lib/workspace-ui-state'
import type { ApiAgentPlan } from '../lib/api-client'

vi.mock('../lib/run-workspace-agent', () => ({
  runWorkspaceAgent: vi.fn(),
  previewWorkspaceAgentPlan: vi.fn(),
}))

import { runWorkspaceAgent, previewWorkspaceAgentPlan } from '../lib/run-workspace-agent'

const mockedRunWorkspaceAgent = vi.mocked(runWorkspaceAgent)
const plan: ApiAgentPlan = {
  version: '1', goal: '提亮', execution: 'ai',
  steps: [{ id: 'edit', tool: 'apply_ai_edit', params: { edit_prompt: '提亮' }, depends_on: [], rationale: '' },
    { id: 'validate', tool: 'validate_result', params: {}, depends_on: ['edit'], rationale: '' }],
}

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
    vi.mocked(previewWorkspaceAgentPlan).mockReset()
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
    expect(wrapper.text()).toContain('局部编辑')
    expect(wrapper.text()).toContain('修图需求（可选）')
    expect(wrapper.find('textarea').exists()).toBe(true)
    expect(wrapper.text()).toContain('预览执行计划')
  })

  it('requires a preview even without a prompt', async () => {
    createDraftWorkspace('workspace-1')
    stageWorkspaceWithImage('workspace-1')

    const wrapper = mount(WorkspaceRightSidebar, {
      props: {
        activeWorkspaceId: 'workspace-1',
      },
    })
    await flushPromises()

    expect(findActionButton(wrapper, '确认计划并执行')?.attributes('disabled')).toBeDefined()
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

    const editorTab = wrapper.findAll('button[role="tab"]').find((button) => button.text() === '局部编辑')
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

    setWorkspaceAgentPlan('workspace-1', plan)
    await flushPromises()
    await findActionButton(wrapper, '确认计划并执行')!.trigger('click')
    await flushPromises()

    expect(mockedRunWorkspaceAgent).toHaveBeenCalled()
    expect(mockedRunWorkspaceAgent.mock.calls[0]?.[2]?.plan).toEqual(plan)
    expect(wrapper.text()).toContain('分析结果')
    expect(wrapper.text()).toContain('风景')
    expect(wrapper.text()).toContain('色彩')
    expect(wrapper.text()).toContain('整体偏灰，饱和度偏低')
    expect(wrapper.text()).toContain('修图指令')
    expect(wrapper.text()).toContain('提升整体饱和度')
    expect(getWorkspace('workspace-1')?.sourceImage).toBe('data:image/png;base64,result')
  })

  it('invalidates a preview when the user changes the request', async () => {
    createDraftWorkspace('workspace-1')
    stageWorkspaceWithImage('workspace-1')
    const wrapper = mount(WorkspaceRightSidebar, { props: { activeWorkspaceId: 'workspace-1' } })
    await flushPromises()
    setWorkspaceAgentPlan('workspace-1', plan)
    setWorkspaceAgentPrompt('workspace-1', '新的要求')
    await flushPromises()
    expect(getWorkspaceAgentPlan('workspace-1')).toBeNull()
    expect(findActionButton(wrapper, '确认计划并执行')?.attributes('disabled')).toBeDefined()
    expect(mockedRunWorkspaceAgent).not.toHaveBeenCalled()
  })

  it('discards a late preview after its prompt changes', async () => {
    createDraftWorkspace('workspace-1')
    stageWorkspaceWithImage('workspace-1')
    let resolvePreview!: (value: Awaited<ReturnType<typeof previewWorkspaceAgentPlan>>) => void
    vi.mocked(previewWorkspaceAgentPlan).mockReturnValue(new Promise((resolve) => { resolvePreview = resolve }))
    const wrapper = mount(WorkspaceRightSidebar, { props: { activeWorkspaceId: 'workspace-1' } })
    await flushPromises()
    await findActionButton(wrapper, '预览执行计划')!.trigger('click')
    setWorkspaceAgentPrompt('workspace-1', '改变背景要求')
    resolvePreview({ analysis: { imageType: 'landscape', imageTypeReason: '', deficiencies: [], summary: '', editPrompt: '' },
      analysisRaw: '{}', images: [], text: null, plan })
    await flushPromises()
    expect(getWorkspaceAgentPlan('workspace-1')).toBeNull()
    expect(wrapper.text()).toContain('输入已变化')
    expect(mockedRunWorkspaceAgent).not.toHaveBeenCalled()
  })
})

import { beforeEach, describe, expect, it } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'

import WorkspaceView from '../views/WorkspaceView.vue'
import {
  clearDraftWorkspaces,
  setWorkspaceEditing,
  stageWorkspaceChanges,
  applyWorkspaceGeneratedImage,
} from '../lib/workspace-session'
import { loadWorkspaceImage } from '../lib/workspace-image-storage'
import { clearWorkspaceImages } from '../lib/workspace-image-storage'

describe('WorkspaceView image actions', () => {
  beforeEach(() => {
    localStorage.clear()
    clearWorkspaceImages()
    clearDraftWorkspaces()
  })

  async function mountWorkspaceView(workspaceId: string) {
    const router = createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/', name: 'home', component: { template: '<div />' } },
        {
          path: '/w/:workspaceId',
          name: 'workspace',
          component: WorkspaceView,
          props: true,
        },
      ],
    })

    stageWorkspaceChanges({
      id: workspaceId,
      title: '测试项目',
      createdAt: Date.now(),
      updatedAt: Date.now(),
      sourceImage: 'data:image/png;base64,original',
      hasSourceImage: true,
    })

    await router.push(`/w/${workspaceId}`)
    await router.isReady()

    const wrapper = mount(WorkspaceView, {
      props: { workspaceId },
      global: {
        plugins: [router],
      },
    })
    await flushPromises()

    return wrapper
  }

  it('shows replace image control when workspace has an image', async () => {
    const wrapper = await mountWorkspaceView('workspace-1')

    expect(wrapper.text()).toContain('更换图片')
  })

  it('replaces workspace image from file input', async () => {
    const wrapper = await mountWorkspaceView('workspace-1')
    const input = wrapper.find('input[type="file"]')

    const file = new File(['image-bytes'], 'next.png', { type: 'image/png' })
    Object.defineProperty(input.element, 'files', {
      value: [file],
    })

    await input.trigger('change')
    await flushPromises()

    expect(wrapper.find('img').attributes('src')).toMatch(/^data:image\/png;base64,/)
  })

  it('shows editing overlay while workspace is being edited', async () => {
    const wrapper = await mountWorkspaceView('workspace-1')

    setWorkspaceEditing('workspace-1', true)
    await flushPromises()

    expect(wrapper.text()).toContain('正在编辑')
  })

  it('updates viewport image after agent result is staged', async () => {
    const wrapper = await mountWorkspaceView('workspace-1')

    await applyWorkspaceGeneratedImage(
      {
        id: 'workspace-1',
        title: '测试项目',
        createdAt: Date.now(),
        updatedAt: Date.now(),
        sourceImage: 'data:image/png;base64,original',
        hasSourceImage: true,
      },
      'data:image/png;base64,edited',
    )
    await flushPromises()

    expect(wrapper.find('img').attributes('src')).toBe('data:image/png;base64,edited')
    expect(await loadWorkspaceImage('workspace-1')).toBeUndefined()
  })
})

import { beforeEach, describe, expect, it } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'

import App from '../App.vue'
import ImageDropzone from '../components/ImageDropzone.vue'
import TopBar from '../components/TopBar.vue'
import WorkspaceView from '../views/WorkspaceView.vue'
import { clearDraftWorkspaces, isWorkspaceDirty } from '../lib/workspace-session'
import { clearWorkspaceImages } from '../lib/workspace-image-storage'

describe('save after image upload', () => {
  beforeEach(() => {
    localStorage.clear()
    clearWorkspaceImages()
    clearDraftWorkspaces()
  })

  it('enables save after uploading an image in workspace view', async () => {
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

    await router.push('/')
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [router],
      },
    })

    const fileButton = wrapper.findAll('button').find((button) => button.text() === '文件')
    await fileButton!.trigger('click')
    await wrapper.vm.$nextTick()

    const newWorkspaceButton = wrapper
      .findAll('[role="menuitem"]')
      .find((item) => item.text().includes('新建工作区'))
    await newWorkspaceButton!.trigger('click')
    await flushPromises()
    await router.isReady()

    const workspaceId = router.currentRoute.value.params.workspaceId as string
    const dropzone = wrapper.findComponent(ImageDropzone)
    expect(dropzone.exists()).toBe(true)

    await dropzone.vm.$emit('select', 'data:image/png;base64,abc')
    await wrapper.vm.$nextTick()

    expect(isWorkspaceDirty(workspaceId)).toBe(true)

    await fileButton!.trigger('click')
    await wrapper.vm.$nextTick()

    const saveItem = wrapper
      .findAll('[role="menuitem"]')
      .find((item) => item.text().includes('保存'))
    expect(saveItem).toBeDefined()
    expect(saveItem!.attributes('disabled')).toBeUndefined()

    const topBar = wrapper.findComponent(TopBar)
    expect(topBar.props('saveEnabled')).toBe(true)
  })
})

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'

import App from '../App.vue'
import * as readImageFile from '../lib/read-image-file'
import { getWorkspace, isWorkspaceDirty } from '../lib/workspace-session'

describe('App', () => {
  beforeEach(() => {
  })

  it('mounts renders properly', async () => {
    const router = createRouter({
      history: createWebHistory(),
      routes: [{ path: '/', component: { template: '<div />' } }],
    })

    await router.push('/')
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [router],
      },
    })
    expect(wrapper.find('header').exists()).toBe(true)
    expect(wrapper.text()).toContain('豆沙包')
    expect(wrapper.text()).toContain('文件')
    expect(wrapper.text()).toContain('编辑')
    expect(wrapper.text()).toContain('视图')
    expect(wrapper.find('button[aria-label="设置"]').exists()).toBe(true)
  })

  it('creates a workspace when clicking 新建工作区', async () => {
    const router = createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/', name: 'home', component: { template: '<div />' } },
        {
          path: '/w/:workspaceId',
          name: 'workspace',
          component: { template: '<div />' },
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

    const buttons = wrapper.findAll('button')
    const fileButton = buttons.find((button) => button.text() === '文件')
    expect(fileButton).toBeDefined()
    await fileButton!.trigger('click')
    await wrapper.vm.$nextTick()

    const menuItems = wrapper.findAll('[role="menuitem"]')
    const newWorkspaceButton = menuItems.find((item) => item.text() === '新建工作区')
    expect(newWorkspaceButton).toBeDefined()
    await newWorkspaceButton!.trigger('click')
    await flushPromises()
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('workspace')
    expect(router.currentRoute.value.params.workspaceId).toBeTruthy()
  })

  it('creates a workspace with image when clicking 打开', async () => {
    vi.spyOn(readImageFile, 'readImageFileAsDataUrl').mockResolvedValue(
      'data:image/png;base64,aW1hZ2UtYnl0ZXM=',
    )

    const router = createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/', name: 'home', component: { template: '<div />' } },
        {
          path: '/w/:workspaceId',
          name: 'workspace',
          component: { template: '<div />' },
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

    const openButton = wrapper
      .findAll('[role="menuitem"]')
      .find((item) => item.text() === '打开')
    expect(openButton).toBeDefined()
    await openButton!.trigger('click')
    await wrapper.vm.$nextTick()

    const input = wrapper.find('input[type="file"][accept="image/*"]')
    expect(input.exists()).toBe(true)

    const file = new File(['image-bytes'], 'photo.png', { type: 'image/png' })
    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true,
    })

    await input.trigger('change')
    await flushPromises()
    await router.isReady()

    const workspaceId = router.currentRoute.value.params.workspaceId as string
    expect(router.currentRoute.value.name).toBe('workspace')
    expect(workspaceId).toBeTruthy()

    const workspace = getWorkspace(workspaceId)
    expect(workspace?.sourceImage).toMatch(/^data:image\/png;base64,/)
    expect(isWorkspaceDirty(workspaceId)).toBe(true)
  })
})

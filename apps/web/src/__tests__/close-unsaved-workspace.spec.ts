import { beforeEach, describe, expect, it } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'

import App from '../App.vue'
import {
  clearDraftWorkspaces,
  getWorkspace,
  isWorkspaceDirty,
  openTabs,
  stageWorkspaceChanges,
} from '../lib/workspace-session'
import { clearWorkspaceImages } from '../lib/workspace-image-storage'

describe('close unsaved workspace', () => {
  beforeEach(() => {
    localStorage.clear()
    clearWorkspaceImages()
    clearDraftWorkspaces()
  })

  async function mountAppOnWorkspace() {
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
      attachTo: document.body,
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

    return { wrapper, router }
  }

  function getCloseTabButton(wrapper: ReturnType<typeof mount>) {
    return wrapper.find('button[aria-label="关闭标签页"]')
  }

  function getCloseDialog() {
    return Array.from(document.body.querySelectorAll('[role="dialog"]')).find((dialog) =>
      dialog.textContent?.includes('关闭工作区'),
    ) as HTMLElement | undefined
  }

  it('prompts before closing a dirty workspace tab', async () => {
    const { wrapper, router } = await mountAppOnWorkspace()
    const workspaceId = router.currentRoute.value.params.workspaceId as string

    stageWorkspaceChanges({
      ...getWorkspace(workspaceId)!,
      sourceImage: 'data:image/png;base64,abc',
    })
    await wrapper.vm.$nextTick()

    expect(isWorkspaceDirty(workspaceId)).toBe(true)
    expect(openTabs.value).toContain(workspaceId)

    await getCloseTabButton(wrapper).trigger('click')
    await wrapper.vm.$nextTick()

    expect(getCloseDialog()?.textContent).toContain('有未保存的更改')
    expect(openTabs.value).toContain(workspaceId)

    wrapper.unmount()
  })

  it('closes tab when choosing discard', async () => {
    const { wrapper, router } = await mountAppOnWorkspace()
    const workspaceId = router.currentRoute.value.params.workspaceId as string

    stageWorkspaceChanges({
      ...getWorkspace(workspaceId)!,
      sourceImage: 'data:image/png;base64,abc',
    })
    await wrapper.vm.$nextTick()

    await getCloseTabButton(wrapper).trigger('click')
    await wrapper.vm.$nextTick()

    const discardButton = Array.from(getCloseDialog()!.querySelectorAll('button')).find(
      (button) => button.textContent?.trim() === '不保存',
    )
    discardButton!.click()
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(openTabs.value).not.toContain(workspaceId)
    expect(router.currentRoute.value.path).toBe('/')

    wrapper.unmount()
  })

  it('keeps tab open when choosing cancel', async () => {
    const { wrapper, router } = await mountAppOnWorkspace()
    const workspaceId = router.currentRoute.value.params.workspaceId as string

    stageWorkspaceChanges({
      ...getWorkspace(workspaceId)!,
      sourceImage: 'data:image/png;base64,abc',
    })
    await wrapper.vm.$nextTick()

    await getCloseTabButton(wrapper).trigger('click')
    await wrapper.vm.$nextTick()

    const cancelButton = Array.from(getCloseDialog()!.querySelectorAll('button')).find(
      (button) => button.textContent?.trim() === '取消',
    )
    cancelButton!.click()
    await wrapper.vm.$nextTick()

    expect(openTabs.value).toContain(workspaceId)
    expect(router.currentRoute.value.params.workspaceId).toBe(workspaceId)

    wrapper.unmount()
  })

  it('closes tab immediately when workspace is clean', async () => {
    const { wrapper, router } = await mountAppOnWorkspace()
    const workspaceId = router.currentRoute.value.params.workspaceId as string

    await getCloseTabButton(wrapper).trigger('click')
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(document.body.textContent).not.toContain('有未保存的更改')
    expect(openTabs.value).not.toContain(workspaceId)
    expect(router.currentRoute.value.path).toBe('/')

    wrapper.unmount()
  })
})

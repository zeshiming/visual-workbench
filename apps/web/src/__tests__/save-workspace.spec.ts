import { beforeEach, describe, expect, it } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'

import App from '../App.vue'
import WorkspaceView from '../views/WorkspaceView.vue'
import {
  clearDraftWorkspaces,
  getWorkspace,
  isWorkspaceDirty,
  stageWorkspaceChanges,
} from '../lib/workspace-session'
import { clearWorkspaceCache } from '../lib/workspace-storage'
import { clearWorkspaceImages } from '../lib/workspace-image-storage'

describe('save workspace', () => {
  beforeEach(() => {
    clearWorkspaceCache()
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

    return { wrapper, router }
  }

  function getSaveMenuItem(wrapper: ReturnType<typeof mount>) {
    return wrapper.findAll('[role="menuitem"]').find((item) => item.text().includes('保存'))
  }

  it('enables save after staging workspace changes', async () => {
    const { wrapper, router } = await mountAppOnWorkspace()
    const workspaceId = router.currentRoute.value.params.workspaceId as string

    stageWorkspaceChanges({
      ...getWorkspace(workspaceId)!,
      sourceImage: 'data:image/png;base64,abc',
    })

    await wrapper.vm.$nextTick()

    expect(isWorkspaceDirty(workspaceId)).toBe(true)

    const fileButton = wrapper.findAll('button').find((button) => button.text() === '文件')
    await fileButton!.trigger('click')
    await wrapper.vm.$nextTick()

    const saveItem = getSaveMenuItem(wrapper)
    expect(saveItem).toBeDefined()
    expect(saveItem!.attributes('disabled')).toBeUndefined()
  })

  it('opens save dialog and persists workspace via save button click', async () => {
    const { wrapper, router } = await mountAppOnWorkspace()
    const workspaceId = router.currentRoute.value.params.workspaceId as string

    stageWorkspaceChanges({
      ...getWorkspace(workspaceId)!,
      sourceImage: 'data:image/png;base64,abc',
    })
    await wrapper.vm.$nextTick()

    const fileButton = wrapper.findAll('button').find((button) => button.text() === '文件')
    await fileButton!.trigger('click')
    await wrapper.vm.$nextTick()

    const saveItem = getSaveMenuItem(wrapper)
    await saveItem!.trigger('click')
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(document.body.textContent).toContain('保存工作区')

    const dialog = document.body.querySelector('[role="dialog"]') as HTMLElement
    const nameInput = dialog.querySelector('input[type="text"]') as HTMLInputElement
    nameInput.value = '测试工作区'
    nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    await wrapper.vm.$nextTick()

    const dialogSaveButton = Array.from(dialog.querySelectorAll('button')).find(
      (button) => button.textContent?.trim() === '保存',
    )
    expect(dialogSaveButton).toBeDefined()
    dialogSaveButton!.click()
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(isWorkspaceDirty(workspaceId)).toBe(false)

    const image = wrapper.find('img[alt="工作区图片"]')
    expect(image.exists()).toBe(true)
    expect(image.attributes('src')).toBe('data:image/png;base64,abc')
  })

  it('saves persisted workspace directly without opening dialog', async () => {
    const { wrapper, router } = await mountAppOnWorkspace()
    const workspaceId = router.currentRoute.value.params.workspaceId as string

    stageWorkspaceChanges({
      ...getWorkspace(workspaceId)!,
      sourceImage: 'data:image/png;base64,abc',
    })
    await wrapper.vm.$nextTick()

    const fileButton = wrapper.findAll('button').find((button) => button.text() === '文件')
    await fileButton!.trigger('click')
    await wrapper.vm.$nextTick()

    const saveItem = getSaveMenuItem(wrapper)
    await saveItem!.trigger('click')
    await flushPromises()
    await wrapper.vm.$nextTick()

    const dialog = document.body.querySelector('[role="dialog"]') as HTMLElement
    const nameInput = dialog.querySelector('input[type="text"]') as HTMLInputElement
    nameInput.value = '测试工作区'
    nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    await wrapper.vm.$nextTick()

    const dialogSaveButton = Array.from(dialog.querySelectorAll('button')).find(
      (button) => button.textContent?.trim() === '保存',
    )
    dialogSaveButton!.click()
    await flushPromises()
    await wrapper.vm.$nextTick()

    stageWorkspaceChanges({
      ...getWorkspace(workspaceId)!,
      sourceImage: 'data:image/png;base64,def',
    })
    await wrapper.vm.$nextTick()

    await fileButton!.trigger('click')
    await wrapper.vm.$nextTick()
    await saveItem!.trigger('click')
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(document.body.textContent).not.toContain('保存工作区')
    expect(isWorkspaceDirty(workspaceId)).toBe(false)
  })

  it('rejects duplicate workspace names', async () => {
    const { wrapper, router } = await mountAppOnWorkspace()
    const firstWorkspaceId = router.currentRoute.value.params.workspaceId as string

    stageWorkspaceChanges({
      ...getWorkspace(firstWorkspaceId)!,
      sourceImage: 'data:image/png;base64,abc',
    })
    await wrapper.vm.$nextTick()

    const fileButton = wrapper.findAll('button').find((button) => button.text() === '文件')
    await fileButton!.trigger('click')
    await wrapper.vm.$nextTick()

    const saveItem = getSaveMenuItem(wrapper)
    await saveItem!.trigger('click')
    await flushPromises()
    await wrapper.vm.$nextTick()

    let dialog = document.body.querySelector('[role="dialog"]') as HTMLElement
    let nameInput = dialog.querySelector('input[type="text"]') as HTMLInputElement
    nameInput.value = '测试工作区'
    nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    await wrapper.vm.$nextTick()

    let dialogSaveButton = Array.from(dialog.querySelectorAll('button')).find(
      (button) => button.textContent?.trim() === '保存',
    )
    dialogSaveButton!.click()
    await flushPromises()
    await wrapper.vm.$nextTick()

    await fileButton!.trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper
      .findAll('[role="menuitem"]')
      .find((item) => item.text().includes('新建工作区'))!
      .trigger('click')
    await flushPromises()
    await router.isReady()

    const secondWorkspaceId = router.currentRoute.value.params.workspaceId as string
    stageWorkspaceChanges({
      ...getWorkspace(secondWorkspaceId)!,
      sourceImage: 'data:image/png;base64,xyz',
    })
    await wrapper.vm.$nextTick()

    await fileButton!.trigger('click')
    await wrapper.vm.$nextTick()
    await saveItem!.trigger('click')
    await flushPromises()
    await wrapper.vm.$nextTick()

    dialog = document.body.querySelector('[role="dialog"]') as HTMLElement
    nameInput = dialog.querySelector('input[type="text"]') as HTMLInputElement
    nameInput.value = '测试工作区'
    nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    await wrapper.vm.$nextTick()

    dialogSaveButton = Array.from(dialog.querySelectorAll('button')).find(
      (button) => button.textContent?.trim() === '保存',
    )
    dialogSaveButton!.click()
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(dialog.textContent).toContain('工作区名称已存在，请使用其他名称')
    expect(isWorkspaceDirty(secondWorkspaceId)).toBe(true)
  })
})

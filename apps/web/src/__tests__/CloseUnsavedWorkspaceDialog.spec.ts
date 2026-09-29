import { describe, expect, it } from 'vitest'

import { mount } from '@vue/test-utils'

import CloseUnsavedWorkspaceDialog from '../components/CloseUnsavedWorkspaceDialog.vue'

describe('CloseUnsavedWorkspaceDialog', () => {
  function getDialog() {
    return document.body.querySelector('[role="dialog"]') as HTMLElement
  }

  it('shows workspace title and emits actions', async () => {
    const wrapper = mount(CloseUnsavedWorkspaceDialog, {
      props: {
        open: true,
        workspaceTitle: '测试工作区',
      },
      attachTo: document.body,
    })

    expect(getDialog().textContent).toContain('关闭工作区')
    expect(getDialog().textContent).toContain('「测试工作区」有未保存的更改')

    const buttons = Array.from(getDialog().querySelectorAll('button'))
    const saveButton = buttons.find((button) => button.textContent?.trim() === '保存')
    const discardButton = buttons.find((button) => button.textContent?.trim() === '不保存')
    const cancelButton = buttons.find((button) => button.textContent?.trim() === '取消')

    expect(saveButton).toBeDefined()
    expect(discardButton).toBeDefined()
    expect(cancelButton).toBeDefined()

    saveButton!.click()
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('save')).toEqual([[]])

    discardButton!.click()
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('discard')).toEqual([[]])

    cancelButton!.click()
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('cancel')).toEqual([[]])

    wrapper.unmount()
  })
})

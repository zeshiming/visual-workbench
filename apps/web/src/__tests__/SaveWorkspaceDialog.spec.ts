import { describe, expect, it } from 'vitest'

import { mount } from '@vue/test-utils'

import SaveWorkspaceDialog from '../components/SaveWorkspaceDialog.vue'

describe('SaveWorkspaceDialog', () => {
  function getDialog() {
    return document.body.querySelector('[role="dialog"]') as HTMLElement
  }

  it('emits confirm when clicking save with a valid name', async () => {
    const wrapper = mount(SaveWorkspaceDialog, {
      props: {
        open: true,
        initialName: '',
      },
      attachTo: document.body,
    })

    const input = getDialog().querySelector('input[type="text"]') as HTMLInputElement
    input.value = '我的海报'
    input.dispatchEvent(new Event('input', { bubbles: true }))
    await wrapper.vm.$nextTick()

    const saveButton = Array.from(getDialog().querySelectorAll('button')).find(
      (button) => button.textContent?.trim() === '保存',
    )
    expect(saveButton).toBeDefined()
    saveButton!.click()
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('confirm')).toEqual([['我的海报']])

    wrapper.unmount()
  })

  it('shows error when submitting an empty name', async () => {
    const wrapper = mount(SaveWorkspaceDialog, {
      props: {
        open: true,
        initialName: '',
      },
      attachTo: document.body,
    })

    const saveButton = Array.from(getDialog().querySelectorAll('button')).find(
      (button) => button.textContent?.trim() === '保存',
    )
    saveButton!.click()
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('confirm')).toBeUndefined()
    expect(getDialog().textContent).toContain('请输入工作区名称')

    wrapper.unmount()
  })
})

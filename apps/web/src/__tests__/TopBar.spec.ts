import { describe, expect, it } from 'vitest'

import { mount } from '@vue/test-utils'

import TopBar from '../components/TopBar.vue'

describe('TopBar save menu', () => {
  const defaultProps = {
    saveEnabled: false,
    exportEnabled: false,
    undoEnabled: false,
    sidebarVisible: true,
    rightSidebarVisible: true,
  }

  async function openFileMenu(wrapper: ReturnType<typeof mount>) {
    const fileButton = wrapper.findAll('button').find((button) => button.text() === '文件')
    await fileButton!.trigger('click')
    await wrapper.vm.$nextTick()
  }

  it('disables save when saveEnabled is false', async () => {
    const wrapper = mount(TopBar, {
      props: {
        ...defaultProps,
        saveEnabled: false,
      },
    })

    await openFileMenu(wrapper)

    const saveItem = wrapper.findAll('[role="menuitem"]').find((item) => item.text().includes('保存'))
    expect(saveItem).toBeDefined()
    expect(saveItem!.attributes('disabled')).toBeUndefined()
    expect(saveItem!.attributes('aria-disabled')).toBe('true')
  })

  it('enables save when saveEnabled is true', async () => {
    const wrapper = mount(TopBar, {
      props: {
        ...defaultProps,
        saveEnabled: true,
      },
    })

    await openFileMenu(wrapper)

    const saveItem = wrapper.findAll('[role="menuitem"]').find((item) => item.text().includes('保存'))
    expect(saveItem).toBeDefined()
    expect(saveItem!.attributes('disabled')).toBeUndefined()
    expect(saveItem!.attributes('aria-disabled')).not.toBe('true')
  })

  it('emits save action when enabled', async () => {
    const wrapper = mount(TopBar, {
      props: {
        ...defaultProps,
        saveEnabled: true,
      },
    })

    await openFileMenu(wrapper)

    const saveItem = wrapper.findAll('[role="menuitem"]').find((item) => item.text().includes('保存'))
    await saveItem!.trigger('click')

    expect(wrapper.emitted('fileAction')).toEqual([['save']])
  })

  it('disables export when exportEnabled is false', async () => {
    const wrapper = mount(TopBar, {
      props: {
        ...defaultProps,
        exportEnabled: false,
      },
    })

    await openFileMenu(wrapper)

    const exportItem = wrapper.findAll('[role="menuitem"]').find((item) => item.text().includes('导出图片'))
    expect(exportItem).toBeDefined()
    expect(exportItem!.attributes('aria-disabled')).toBe('true')
  })

  it('emits export action when enabled', async () => {
    const wrapper = mount(TopBar, {
      props: {
        ...defaultProps,
        exportEnabled: true,
      },
    })

    await openFileMenu(wrapper)

    const exportItem = wrapper.findAll('[role="menuitem"]').find((item) => item.text().includes('导出图片'))
    await exportItem!.trigger('click')

    expect(wrapper.emitted('fileAction')).toEqual([['export-image']])
  })

  it('shows export shortcut in file menu', async () => {
    const wrapper = mount(TopBar, {
      props: {
        ...defaultProps,
        exportEnabled: true,
      },
    })

    await openFileMenu(wrapper)

    expect(wrapper.get('[role="menu"]').text()).toMatch(/导出图片/)
    expect(wrapper.get('[role="menu"]').text()).toMatch(/⌘⇧E|Ctrl\+Shift\+E/)
  })

  it('emits toggleSidebar when clicking sidebar button', async () => {
    const wrapper = mount(TopBar, {
      props: defaultProps,
    })

    await wrapper.get('button[aria-label="隐藏侧边栏"]').trigger('click')

    expect(wrapper.emitted('toggleSidebar')).toEqual([[]])
  })

  it('emits toggleRightSidebar when clicking right sidebar button', async () => {
    const wrapper = mount(TopBar, {
      props: defaultProps,
    })

    await wrapper.get('button[aria-label="隐藏编辑面板"]').trigger('click')

    expect(wrapper.emitted('toggleRightSidebar')).toEqual([[]])
  })
})

describe('TopBar view menu', () => {
  const defaultProps = {
    saveEnabled: false,
    exportEnabled: false,
    undoEnabled: false,
    sidebarVisible: true,
    rightSidebarVisible: true,
  }

  async function openViewMenu(wrapper: ReturnType<typeof mount>) {
    const viewButton = wrapper.findAll('button').find((button) => button.text() === '视图')
    await viewButton!.trigger('click')
    await wrapper.vm.$nextTick()
  }

  it('shows sidebar shortcuts in view menu', async () => {
    const wrapper = mount(TopBar, {
      props: defaultProps,
    })

    await openViewMenu(wrapper)

    const menuText = wrapper.get('[role="menu"]').text()
    expect(menuText).toContain('项目栏')
    expect(menuText).toContain('编辑面板')
    expect(menuText).toMatch(/⌘B|Ctrl\+B/)
    expect(menuText).toMatch(/⌘⇧B|Ctrl\+Shift\+B/)
  })

  it('emits toggleSidebar from view menu', async () => {
    const wrapper = mount(TopBar, {
      props: defaultProps,
    })

    await openViewMenu(wrapper)

    const sidebarItem = wrapper
      .findAll('[role="menuitemcheckbox"]')
      .find((item) => item.text().includes('项目栏'))
    await sidebarItem!.trigger('click')

    expect(wrapper.emitted('toggleSidebar')).toEqual([[]])
  })

  it('shows shortcut badges on sidebar toggle buttons', () => {
    const wrapper = mount(TopBar, {
      props: defaultProps,
    })

    const badges = wrapper.findAll('kbd')
    expect(badges.length).toBeGreaterThanOrEqual(2)
    expect(badges.some((badge) => badge.text().match(/⌘B|Ctrl\+B/))).toBe(true)
    expect(badges.some((badge) => badge.text().match(/⌘⇧B|Ctrl\+Shift\+B/))).toBe(true)
  })
})

describe('TopBar edit menu', () => {
  const defaultProps = {
    saveEnabled: false,
    exportEnabled: false,
    undoEnabled: true,
    sidebarVisible: true,
    rightSidebarVisible: true,
  }

  async function openEditMenu(wrapper: ReturnType<typeof mount>) {
    const editButton = wrapper.findAll('button').find((button) => button.text() === '编辑')
    await editButton!.trigger('click')
    await wrapper.vm.$nextTick()
  }

  it('emits undo action from edit menu', async () => {
    const wrapper = mount(TopBar, {
      props: defaultProps,
    })

    await openEditMenu(wrapper)

    const undoItem = wrapper.findAll('[role="menuitem"]').find((item) => item.text().includes('撤回更改'))
    await undoItem!.trigger('click')

    expect(wrapper.emitted('editAction')).toEqual([['undo']])
  })

  it('shows undo shortcut in edit menu', async () => {
    const wrapper = mount(TopBar, {
      props: defaultProps,
    })

    await openEditMenu(wrapper)

    expect(wrapper.get('[role="menu"]').text()).toMatch(/撤回更改/)
    expect(wrapper.get('[role="menu"]').text()).toMatch(/⌘Z|Ctrl\+Z/)
  })
})

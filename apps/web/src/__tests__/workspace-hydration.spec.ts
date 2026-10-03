import { beforeEach, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import WorkspaceView from '../views/WorkspaceView.vue'
import { clearDraftWorkspaces, stageWorkspaceChanges } from '../lib/workspace-session'
import { hydrateWorkspaceImage } from '../lib/workspace-storage'
import type { Workspace } from '../types/workspace'

vi.mock('../lib/workspace-storage', async (original) => ({
  ...await original<typeof import('../lib/workspace-storage')>(),
  hydrateWorkspaceImage: vi.fn(),
}))

function item(id: string): Workspace {
  return { id, title: id, hasSourceImage: true, createdAt: 1, updatedAt: 1 }
}
function view() {
  return mount(WorkspaceView, {
    props: { workspaceId: 'a' },
    global: { stubs: { AssetLibrary: true, WorkspaceImageViewport: { props: ['src'], template: '<img :src="src" />' } } },
  })
}
beforeEach(() => { clearDraftWorkspaces(); vi.mocked(hydrateWorkspaceImage).mockReset() })

it('ignores a late image from the previously selected workspace', async () => {
  stageWorkspaceChanges(item('a'))
  stageWorkspaceChanges(item('b'))
  let resolveOld!: (image: Workspace) => void
  vi.mocked(hydrateWorkspaceImage).mockImplementation((workspace) => workspace.id === 'a'
    ? new Promise((resolve) => { resolveOld = resolve })
    : Promise.resolve({ ...workspace, sourceImage: 'image-b' }))
  const wrapper = view()
  await wrapper.setProps({ workspaceId: 'b' })
  await flushPromises()
  expect(wrapper.find('img').attributes('src')).toBe('image-b')
  resolveOld({ ...item('a'), sourceImage: 'image-a' })
  await flushPromises()
  expect(wrapper.find('img').attributes('src')).toBe('image-b')
  wrapper.unmount()
})

it('shows a retryable error when a saved image cannot be loaded', async () => {
  stageWorkspaceChanges(item('a'))
  vi.mocked(hydrateWorkspaceImage).mockResolvedValueOnce(item('a'))
    .mockResolvedValueOnce({ ...item('a'), sourceImage: 'recovered' })
  const wrapper = view()
  await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  await wrapper.find('[role="alert"] button').trigger('click')
  await flushPromises()
  expect(wrapper.find('img').attributes('src')).toBe('recovered')
  wrapper.unmount()
})

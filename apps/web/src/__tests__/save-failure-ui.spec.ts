import './fixtures/persistence-backend'
import { expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import App from '../App.vue'
import { saveWorkspace, clearWorkspaceCache } from '../lib/workspace-storage'
import { stageWorkspaceChanges, clearDraftWorkspaces, isWorkspaceDirty, addOpenWorkspace } from '../lib/workspace-session'
import * as api from '../lib/api-client'

it('shows direct-save failure outside the naming dialog and permits retry', async () => {
  clearDraftWorkspaces()
  clearWorkspaceCache()
  const item = { id: 'saved', title: '已保存项目', createdAt: 1, updatedAt: 1 }
  await saveWorkspace(item)
  stageWorkspaceChanges({ ...item, sourceImage: 'changed' })
  addOpenWorkspace(item.id)
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/w/:workspaceId', name: 'workspace', component: { template: '<div />' } },
  ] })
  await router.push('/w/saved')
  const wrapper = mount(App, { global: { plugins: [router], stubs: {
    RouteTransition: true, WorkspaceRightSidebar: true, SavedProjectSidebar: true,
    TopBar: { template: '<button data-save @click="$emit(\'file-action\', \'save\')">save</button>' },
  } } })
  await flushPromises()
  vi.mocked(api.commitBackendWorkspace).mockRejectedValueOnce(new Error('offline'))
  await wrapper.find('[data-save]').trigger('click')
  await flushPromises()
  expect(wrapper.find('[role="alert"]').text()).toContain('offline')
  expect(isWorkspaceDirty('saved')).toBe(true)
  await wrapper.find('[role="alert"] button').trigger('click')
  await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  expect(isWorkspaceDirty('saved')).toBe(false)
  wrapper.unmount()
})

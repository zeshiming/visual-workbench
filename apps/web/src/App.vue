<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { syncDocumentTitle } from '@/lib/sync-document-title'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import RouteTransition from '@/components/RouteTransition.vue'
import CloseUnsavedWorkspaceDialog from '@/components/CloseUnsavedWorkspaceDialog.vue'
import SaveWorkspaceDialog from '@/components/SaveWorkspaceDialog.vue'
import SavedProjectSidebar from '@/components/SavedProjectSidebar.vue'
import WorkspaceRightSidebar from '@/components/WorkspaceRightSidebar.vue'
import TabBar from '@/components/TabBar.vue'
import TopBar from '@/components/TopBar.vue'
import { openNewWorkspace, openNewWorkspaceWithImage } from '@/lib/open-new-workspace'
import { pickImageFile, readImageFileAsDataUrl } from '@/lib/read-image-file'
import { handleAppShortcut } from '@/lib/app-shortcuts'
import { canExportWorkspace, exportWorkspaceImage } from '@/lib/export-workspace-image'
import {
  addOpenWorkspace,
  addSettingsTab,
  canUndoWorkspaceImage,
  closeTab,
  dirtyWorkspaceIds,
  getWorkspace,
  isSettingsTab,
  isWorkspaceDirty,
  isWorkspaceEditing,
  openTabs,
  persistWorkspace,
  removeSavedProject,
  SETTINGS_TAB_ID,
  undoWorkspaceImageChange,
  workspaceContentRevision,
} from '@/lib/workspace-session'
import { initAppSettings } from '@/lib/config-storage'
import { syncWorkspacesFromBackend } from '@/lib/workspace-storage'
import { workspaceUndoRevision } from '@/lib/workspace-image-history'
import {
  DEFAULT_WORKSPACE_TITLE,
  getDisplayWorkspaceTitle,
  isPersistedWorkspace,
  isWorkspaceNameTaken,
  savedWorkspacesRevision,
} from '@/lib/workspace-storage'
import type { Workspace } from '@/types/workspace'

const router = useRouter()
const route = useRoute()
const { t, locale } = useI18n()
const transitionDirection = ref<'forward' | 'back'>('forward')
const saveDialogOpen = ref(false)
const saveDialogInitialName = ref('')
const saveTargetWorkspace = ref<Workspace | null>(null)
const saveError = ref('')
const isSavingWorkspace = ref(false)
const closeDialogOpen = ref(false)
const closeTargetTabId = ref<string | null>(null)
const sidebarVisible = ref(true)
const rightSidebarVisible = ref(true)
const openImageInputRef = ref<HTMLInputElement | null>(null)

const appTabs = computed(() => {
  // Read reactive deps: workspace cache + open tabs + dirty state
  savedWorkspacesRevision.value
  return openTabs.value.flatMap((id) => {
    if (isSettingsTab(id)) {
      return [{ id, title: t('common.settings'), isDirty: false }]
    }

    const workspace = getWorkspace(id)
    if (!workspace) {
      return []
    }

    return [
      {
        id,
        title: getDisplayWorkspaceTitle(workspace.title),
        isDirty: isWorkspaceDirty(id),
      },
    ]
  })
})

const activeTabId = computed(() => {
  if (route.name === 'settings') {
    return SETTINGS_TAB_ID
  }

  if (route.name === 'workspace' && typeof route.params.workspaceId === 'string') {
    return route.params.workspaceId
  }

  const tabs = appTabs.value
  return tabs.length > 0 ? tabs[tabs.length - 1]!.id : ''
})

const activeWorkspaceId = computed(() => {
  if (route.name === 'workspace' && typeof route.params.workspaceId === 'string') {
    return route.params.workspaceId
  }

  return ''
})

syncDocumentTitle({
  appName: () => {
    locale.value
    return t('app.name')
  },
  pageTitle: () => {
    locale.value
    workspaceContentRevision.value
    route.name
    route.params.workspaceId

    if (route.name === 'settings') {
      return t('common.settings')
    }

    if (route.name === 'workspace') {
      const workspaceId = activeWorkspaceId.value
      const workspace = workspaceId ? getWorkspace(workspaceId) : null
      if (workspace) {
        return getDisplayWorkspaceTitle(workspace.title)
      }
    }

    return t('home.mainWorkspace')
  },
})

const canSaveActiveWorkspace = computed(() => {
  const workspaceId = activeWorkspaceId.value
  if (!workspaceId) {
    return false
  }

  return dirtyWorkspaceIds.value.has(workspaceId)
})

const canUndoActiveWorkspace = computed(() => {
  workspaceUndoRevision.value

  const workspaceId = activeWorkspaceId.value
  if (!workspaceId || isWorkspaceEditing(workspaceId)) {
    return false
  }

  return canUndoWorkspaceImage(workspaceId)
})

const canExportActiveWorkspace = computed(() => {
  const workspaceId = activeWorkspaceId.value
  if (!workspaceId || isWorkspaceEditing(workspaceId)) {
    return false
  }

  return canExportWorkspace(getWorkspace(workspaceId))
})

const closeTargetWorkspaceTitle = computed(() => {
  const tabId = closeTargetTabId.value
  if (!tabId) {
    return ''
  }

  return getDisplayWorkspaceTitle(getWorkspace(tabId)?.title ?? DEFAULT_WORKSPACE_TITLE)
})

router.beforeEach((to, from) => {
  if (to.name === 'workspace' && typeof to.params.workspaceId === 'string') {
    addOpenWorkspace(to.params.workspaceId)
  }

  if (to.name === 'settings') {
    addSettingsTab()
    transitionDirection.value = 'forward'
  } else if (from.name === 'settings') {
    transitionDirection.value = 'back'
  }
})

function openSettings() {
  addSettingsTab()

  if (route.name !== 'settings') {
    router.push('/settings')
  }
}

function toggleSidebar() {
  sidebarVisible.value = !sidebarVisible.value
}

function toggleRightSidebar() {
  rightSidebarVisible.value = !rightSidebarVisible.value
}

function requestOpenImage(): void {
  openImageInputRef.value?.click()
}

async function handleOpenImageInput(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files ? pickImageFile(input.files) : null
  input.value = ''

  if (!file) {
    return
  }

  const dataUrl = await readImageFileAsDataUrl(file)
  openNewWorkspaceWithImage(router, dataUrl)
}

function handleFileAction(action: 'new-workspace' | 'new-video-workspace' | 'open' | 'save' | 'export-image') {
  if (action === 'new-workspace') {
    openNewWorkspace(router)
    return
  }

  if (action === 'open') {
    requestOpenImage()
    return
  }

  if (action === 'save') {
    requestSaveActiveWorkspace()
    return
  }

  if (action === 'export-image') {
    void requestExportActiveWorkspace()
  }
}

function handleEditAction(action: 'undo') {
  if (action === 'undo') {
    void requestUndoActiveWorkspace()
  }
}

async function requestUndoActiveWorkspace(): Promise<void> {
  const workspaceId = activeWorkspaceId.value
  if (!workspaceId || !canUndoActiveWorkspace.value) {
    return
  }

  await undoWorkspaceImageChange(workspaceId)
}

async function requestExportActiveWorkspace(): Promise<void> {
  const workspaceId = activeWorkspaceId.value
  if (!workspaceId || !canExportActiveWorkspace.value) {
    return
  }

  const workspace = getWorkspace(workspaceId)
  if (!workspace) {
    return
  }

  try {
    await exportWorkspaceImage(workspace)
  } catch {
    // 导出失败时静默处理；Editor 面板会显示具体错误
  }
}

function openSaveDialog(workspace: Workspace): void {
  saveError.value = ''
  saveTargetWorkspace.value = { ...workspace }
  saveDialogInitialName.value =
    workspace.title === DEFAULT_WORKSPACE_TITLE ? '' : workspace.title
  saveDialogOpen.value = true
}

async function saveWorkspaceDirectly(
  workspace: Workspace,
  options?: { pendingCloseTabId?: string | null },
): Promise<void> {
  isSavingWorkspace.value = true
  saveError.value = ''

  try {
    await persistWorkspace(workspace)

    const pendingCloseTabId = options?.pendingCloseTabId ?? closeTargetTabId.value
    if (pendingCloseTabId) {
      closeTargetTabId.value = null
      performCloseTab(pendingCloseTabId)
    }
  } catch (error) {
    saveError.value = error instanceof Error ? error.message : t('errors.saveFailed')
  } finally {
    isSavingWorkspace.value = false
  }
}

function requestSaveActiveWorkspace(): void {
  const workspaceId = activeWorkspaceId.value
  if (!workspaceId || !dirtyWorkspaceIds.value.has(workspaceId)) {
    return
  }

  const workspace = getWorkspace(workspaceId)
  if (!workspace) {
    return
  }

  if (isPersistedWorkspace(workspaceId)) {
    void saveWorkspaceDirectly(workspace)
    return
  }

  openSaveDialog(workspace)
}

async function confirmSaveWorkspace(name: string): Promise<void> {
  const workspace = saveTargetWorkspace.value
  if (!workspace) {
    saveError.value = t('errors.workspaceNotFound')
    return
  }

  if (isWorkspaceNameTaken(name, workspace.id)) {
    saveError.value = t('errors.workspaceNameTaken')
    return
  }

  isSavingWorkspace.value = true
  saveError.value = ''

  try {
    await persistWorkspace({
      ...workspace,
      title: name,
    })
    saveDialogOpen.value = false
    saveTargetWorkspace.value = null

    const pendingCloseTabId = closeTargetTabId.value
    if (pendingCloseTabId) {
      closeTargetTabId.value = null
      performCloseTab(pendingCloseTabId)
    }
  } catch (error) {
    saveError.value = error instanceof Error ? error.message : t('errors.saveFailed')
  } finally {
    isSavingWorkspace.value = false
  }
}

function cancelSaveWorkspace(): void {
  saveDialogOpen.value = false
  saveTargetWorkspace.value = null
  saveError.value = ''

  if (closeTargetTabId.value) {
    closeDialogOpen.value = true
  }
}

function onDocumentKeyDown(event: KeyboardEvent): void {
  if (
    handleAppShortcut(event, {
      save: requestSaveActiveWorkspace,
      undo: () => {
        void requestUndoActiveWorkspace()
      },
      exportImage: () => {
        void requestExportActiveWorkspace()
      },
      toggleSidebar,
      toggleRightSidebar,
    })
  ) {
    event.preventDefault()
  }
}

onMounted(() => {
  document.addEventListener('keydown', onDocumentKeyDown)

  // Initialize all data from backend
  Promise.all([
    initAppSettings(),
    syncWorkspacesFromBackend(),
  ]).catch(() => {
    // Silently fail — will use in-memory defaults
  })
})

onUnmounted(() => {
  document.removeEventListener('keydown', onDocumentKeyDown)
})

function selectTab(tabId: string) {
  if (tabId === activeTabId.value) {
    return
  }

  if (isSettingsTab(tabId)) {
    void router.push('/settings')
    return
  }

  void router.push({
    name: 'workspace',
    params: { workspaceId: tabId },
  })
}

function openSavedProject(workspaceId: string) {
  addOpenWorkspace(workspaceId)

  if (route.name === 'workspace' && route.params.workspaceId === workspaceId) {
    return
  }

  void router.push({
    name: 'workspace',
    params: { workspaceId },
  })
}

function navigateAfterCloseTab(nextTabId: string | null) {
  if (nextTabId) {
    if (isSettingsTab(nextTabId)) {
      void router.replace('/settings')
      return
    }

    void router.replace({
      name: 'workspace',
      params: { workspaceId: nextTabId },
    })
    return
  }

  void router.replace('/')
}

function performCloseTab(tabId: string): void {
  const isClosingActiveTab =
    (route.name === 'settings' && tabId === SETTINGS_TAB_ID) ||
    (route.name === 'workspace' && route.params.workspaceId === tabId)

  const nextTabId = closeTab(tabId)

  if (!isClosingActiveTab) {
    return
  }

  navigateAfterCloseTab(nextTabId)
}

function closeAppTab(tabId: string): void {
  if (isSettingsTab(tabId) || !isWorkspaceDirty(tabId)) {
    performCloseTab(tabId)
    return
  }

  closeTargetTabId.value = tabId
  closeDialogOpen.value = true
}

function cancelCloseUnsavedWorkspace(): void {
  closeDialogOpen.value = false
  closeTargetTabId.value = null
}

function discardCloseUnsavedWorkspace(): void {
  const tabId = closeTargetTabId.value
  if (!tabId) {
    return
  }

  closeDialogOpen.value = false
  closeTargetTabId.value = null
  performCloseTab(tabId)
}

function saveCloseUnsavedWorkspace(): void {
  const tabId = closeTargetTabId.value
  if (!tabId) {
    return
  }

  const workspace = getWorkspace(tabId)
  if (!workspace) {
    cancelCloseUnsavedWorkspace()
    return
  }

  closeDialogOpen.value = false

  if (isPersistedWorkspace(tabId)) {
    void saveWorkspaceDirectly(workspace, { pendingCloseTabId: tabId })
    return
  }

  openSaveDialog(workspace)
}

async function handleDeleteProject(workspaceId: string): Promise<void> {
  const isViewingDeletedProject =
    route.name === 'workspace' && route.params.workspaceId === workspaceId

  const nextTabId = await removeSavedProject(workspaceId)

  if (isViewingDeletedProject) {
    navigateAfterCloseTab(nextTabId)
  }
}

</script>

<template>
  <div class="flex min-h-dvh flex-col bg-app text-app-foreground">
    <TopBar
      :save-enabled="canSaveActiveWorkspace"
      :export-enabled="canExportActiveWorkspace"
      :undo-enabled="canUndoActiveWorkspace"
      :sidebar-visible="sidebarVisible"
      :right-sidebar-visible="rightSidebarVisible"
      @settings-click="openSettings"
      @toggle-sidebar="toggleSidebar"
      @toggle-right-sidebar="toggleRightSidebar"
      @file-action="handleFileAction"
      @edit-action="handleEditAction"
    />
    <div class="flex min-h-0 flex-1">
      <SavedProjectSidebar
        v-show="sidebarVisible"
        :active-workspace-id="activeWorkspaceId"
        @select="openSavedProject"
        @delete="handleDeleteProject"
      />
      <div class="flex min-h-0 min-w-0 flex-1 flex-col">
        <TabBar
          v-if="appTabs.length"
          :tabs="appTabs"
          :active-tab-id="activeTabId"
          @select="selectTab"
          @close="closeAppTab"
        />
        <main class="flex min-h-0 flex-1 flex-col overflow-hidden bg-app-surface">
          <RouteTransition :direction="transitionDirection" />
        </main>
      </div>
      <WorkspaceRightSidebar
        v-show="rightSidebarVisible"
        :active-workspace-id="activeWorkspaceId"
      />
    </div>

    <SaveWorkspaceDialog
      :open="saveDialogOpen"
      :initial-name="saveDialogInitialName"
      :error-message="saveError"
      :saving="isSavingWorkspace"
      @confirm="confirmSaveWorkspace"
      @cancel="cancelSaveWorkspace"
    />

    <CloseUnsavedWorkspaceDialog
      :open="closeDialogOpen"
      :workspace-title="closeTargetWorkspaceTitle"
      @save="saveCloseUnsavedWorkspace"
      @discard="discardCloseUnsavedWorkspace"
      @cancel="cancelCloseUnsavedWorkspace"
    />

    <input
      ref="openImageInputRef"
      type="file"
      accept="image/*"
      class="hidden"
      @change="handleOpenImageInput"
    />
  </div>
</template>

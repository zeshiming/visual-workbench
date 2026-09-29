<script setup lang="ts">
import { Check, PanelLeft, PanelLeftClose, PanelRight, PanelRightClose, Settings } from '@lucide/vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { logoUrl } from '@/lib/app-brand'

const { t } = useI18n()

const editMenuItems = computed(() => [{ id: 'undo' as const, label: t('menu.undo'), shortcut: true }])

const fileMenuItems = computed(() => [
  { id: 'new-workspace' as const, label: t('menu.newWorkspace') },
  { id: 'open' as const, label: t('common.open'), dividerAfter: true },
  { id: 'save' as const, label: t('menu.save'), shortcut: 'save' as const },
  { id: 'export-image' as const, label: t('menu.exportImage'), shortcut: 'export' as const },
])

const viewMenuItems = computed(() => [
  { id: 'toggle-sidebar' as const, label: t('menu.projectSidebar'), shortcut: 'left' as const },
  { id: 'toggle-right-sidebar' as const, label: t('menu.editorPanel'), shortcut: 'right' as const },
])

const GITHUB_URL = 'https://github.com/dongguacute/doushabao'

type FileMenuAction = (typeof fileMenuItems.value)[number]['id']
type ViewMenuAction = (typeof viewMenuItems.value)[number]['id']
type EditMenuAction = (typeof editMenuItems.value)[number]['id']

const props = defineProps<{
  saveEnabled: boolean
  exportEnabled: boolean
  undoEnabled: boolean
  sidebarVisible: boolean
  rightSidebarVisible: boolean
}>()

const emit = defineEmits<{
  settingsClick: []
  toggleSidebar: []
  toggleRightSidebar: []
  fileAction: [action: FileMenuAction]
  editAction: [action: EditMenuAction]
}>()

const fileMenuOpen = ref(false)
const viewMenuOpen = ref(false)
const editMenuOpen = ref(false)
const fileMenuRef = ref<HTMLElement | null>(null)
const viewMenuRef = ref<HTMLElement | null>(null)
const editMenuRef = ref<HTMLElement | null>(null)
const isMac = /Mac|iPhone|iPad/i.test(navigator.userAgent)
const saveShortcutLabel = isMac ? '⌘S' : 'Ctrl+S'
const exportShortcutLabel = isMac ? '⌘⇧E' : 'Ctrl+Shift+E'
const undoShortcutLabel = isMac ? '⌘Z' : 'Ctrl+Z'
const leftSidebarShortcutLabel = isMac ? '⌘B' : 'Ctrl+B'
const rightSidebarShortcutLabel = isMac ? '⌘⇧B' : 'Ctrl+Shift+B'

// ── Desktop (Electron) detection ───────────────────────────────
const isDesktop = ref(false)
const desktopPlatform = ref('')
const isMacDesktop = computed(() => isDesktop.value && /darwin/i.test(desktopPlatform.value))
const isWinLinuxDesktop = computed(() => isDesktop.value && !/darwin/i.test(desktopPlatform.value))
const isWindowMaximized = ref(false)

function setupDesktopEnv() {
  if (!window.electronAPI) return
  isDesktop.value = true
  window.electronAPI.getAppInfo().then((info) => {
    desktopPlatform.value = info.platform
  })
  window.electronAPI.isMaximized().then((max) => {
    isWindowMaximized.value = max
  })
  window.electronAPI.onMaximizedChanged((maximized) => {
    isWindowMaximized.value = maximized
  })
}

function minimizeWindow() {
  window.electronAPI?.minimizeWindow()
}

function maximizeWindow() {
  window.electronAPI?.maximizeWindow()
}

function closeWindow() {
  window.electronAPI?.closeWindow()
}

const shortcutBadgeClass =
  'rounded border border-app-border bg-app px-1 py-0.5 text-[10px] font-normal leading-none text-app-subtle'

function shortcutLabelForViewItem(shortcut: 'left' | 'right'): string {
  return shortcut === 'left' ? leftSidebarShortcutLabel : rightSidebarShortcutLabel
}

function shortcutLabelForFileItem(shortcut: 'save' | 'export'): string {
  return shortcut === 'save' ? saveShortcutLabel : exportShortcutLabel
}

function isFileItemDisabled(id: FileMenuAction): boolean {
  if (id === 'save') {
    return !props.saveEnabled
  }

  if (id === 'export-image') {
    return !props.exportEnabled
  }

  return false
}

function isViewItemChecked(id: ViewMenuAction): boolean {
  return id === 'toggle-sidebar' ? props.sidebarVisible : props.rightSidebarVisible
}

function closeAllMenus() {
  fileMenuOpen.value = false
  viewMenuOpen.value = false
  editMenuOpen.value = false
}

function toggleFileMenu() {
  viewMenuOpen.value = false
  editMenuOpen.value = false
  fileMenuOpen.value = !fileMenuOpen.value
}

function toggleViewMenu() {
  fileMenuOpen.value = false
  editMenuOpen.value = false
  viewMenuOpen.value = !viewMenuOpen.value
}

function toggleEditMenu() {
  fileMenuOpen.value = false
  viewMenuOpen.value = false
  editMenuOpen.value = !editMenuOpen.value
}

function onFileAction(action: FileMenuAction) {
  if (isFileItemDisabled(action)) {
    return
  }

  emit('fileAction', action)
  closeAllMenus()
}

function onViewAction(action: ViewMenuAction) {
  if (action === 'toggle-sidebar') {
    emit('toggleSidebar')
  } else {
    emit('toggleRightSidebar')
  }

  closeAllMenus()
}

function onEditAction(action: EditMenuAction) {
  if (action === 'undo' && !props.undoEnabled) {
    return
  }

  emit('editAction', action)
  closeAllMenus()
}

function onDocumentPointerDown(event: PointerEvent) {
  const target = event.target as Node

  if (fileMenuOpen.value && !fileMenuRef.value?.contains(target)) {
    fileMenuOpen.value = false
  }

  if (viewMenuOpen.value && !viewMenuRef.value?.contains(target)) {
    viewMenuOpen.value = false
  }

  if (editMenuOpen.value && !editMenuRef.value?.contains(target)) {
    editMenuOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
  setupDesktopEnv()
})
onUnmounted(() => document.removeEventListener('pointerdown', onDocumentPointerDown))
</script>

<template>
  <header
    class="relative z-50 flex h-10 shrink-0 items-center justify-between border-b border-app-border bg-app/95 px-3 backdrop-blur-sm select-none"
    :class="{
      'app-drag': isDesktop,
      'pl-20': isMacDesktop,
    }"
  >
    <nav class="flex min-w-0 items-center gap-3" :class="{ 'app-no-drag': isDesktop }">
      <div class="flex shrink-0 items-center gap-2">
        <img
          :src="logoUrl"
          :alt="t('app.name')"
          class="size-6 shrink-0 object-contain"
          width="24"
          height="24"
        />
        <span class="text-sm font-semibold tracking-tight text-app-foreground">{{ t('app.name') }}</span>
      </div>

      <div class="flex items-center gap-0.5">
        <div ref="fileMenuRef" class="relative">
          <button
            type="button"
            class="rounded-md px-2.5 py-1 text-sm transition-colors"
            :class="
              fileMenuOpen
                ? 'bg-app-accent text-app-foreground'
                : 'text-app-muted hover:bg-app-accent hover:text-app-foreground'
            "
            aria-haspopup="menu"
            :aria-expanded="fileMenuOpen"
            @click.stop="toggleFileMenu"
          >
            {{ t('menu.file') }}
          </button>

          <div
            v-if="fileMenuOpen"
            class="absolute left-0 top-full z-50 min-w-36 pt-1"
            role="presentation"
            @pointerdown.stop
          >
            <div
              class="overflow-hidden rounded-lg border border-app-border bg-app-elevated py-1 shadow-lg shadow-black/10"
              role="menu"
            >
              <template v-for="item in fileMenuItems" :key="item.id">
                <button
                  type="button"
                  class="flex w-full items-center px-3 py-1.5 text-left text-sm transition-colors"
                  :class="
                    isFileItemDisabled(item.id)
                      ? 'cursor-not-allowed text-app-subtle'
                      : 'text-app-foreground hover:bg-app-accent'
                  "
                  role="menuitem"
                  :aria-disabled="isFileItemDisabled(item.id)"
                  @click="onFileAction(item.id)"
                >
                  <span>{{ item.label }}</span>
                  <span
                    v-if="'shortcut' in item && item.shortcut"
                    class="ml-auto pl-4 text-xs text-app-subtle"
                  >
                    {{ shortcutLabelForFileItem(item.shortcut) }}
                  </span>
                </button>
                <div
                  v-if="'dividerAfter' in item && item.dividerAfter"
                  class="my-1 border-t border-app-border"
                  role="separator"
                />
              </template>
            </div>
          </div>
        </div>

        <div ref="viewMenuRef" class="relative">
          <button
            type="button"
            class="rounded-md px-2.5 py-1 text-sm transition-colors"
            :class="
              viewMenuOpen
                ? 'bg-app-accent text-app-foreground'
                : 'text-app-muted hover:bg-app-accent hover:text-app-foreground'
            "
            aria-haspopup="menu"
            :aria-expanded="viewMenuOpen"
            @click.stop="toggleViewMenu"
          >
            {{ t('menu.view') }}
          </button>

          <div
            v-if="viewMenuOpen"
            class="absolute left-0 top-full z-50 min-w-44 pt-1"
            role="presentation"
            @pointerdown.stop
          >
            <div
              class="overflow-hidden rounded-lg border border-app-border bg-app-elevated py-1 shadow-lg shadow-black/10"
              role="menu"
            >
              <button
                v-for="item in viewMenuItems"
                :key="item.id"
                type="button"
                class="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-app-foreground transition-colors hover:bg-app-accent"
                role="menuitemcheckbox"
                :aria-checked="isViewItemChecked(item.id)"
                @click="onViewAction(item.id)"
              >
                <Check
                  v-if="isViewItemChecked(item.id)"
                  :size="14"
                  :stroke-width="2"
                  class="shrink-0 text-app-muted"
                />
                <span v-else class="inline-block w-3.5 shrink-0" aria-hidden="true" />
                <span>{{ item.label }}</span>
                <span class="ml-auto pl-4 text-xs text-app-subtle">
                  {{ shortcutLabelForViewItem(item.shortcut) }}
                </span>
              </button>
            </div>
          </div>
        </div>

        <div ref="editMenuRef" class="relative">
          <button
            type="button"
            class="rounded-md px-2.5 py-1 text-sm transition-colors"
            :class="
              editMenuOpen
                ? 'bg-app-accent text-app-foreground'
                : 'text-app-muted hover:bg-app-accent hover:text-app-foreground'
            "
            aria-haspopup="menu"
            :aria-expanded="editMenuOpen"
            @click.stop="toggleEditMenu"
          >
            {{ t('menu.edit') }}
          </button>

          <div
            v-if="editMenuOpen"
            class="absolute left-0 top-full z-50 min-w-40 pt-1"
            role="presentation"
            @pointerdown.stop
          >
            <div
              class="overflow-hidden rounded-lg border border-app-border bg-app-elevated py-1 shadow-lg shadow-black/10"
              role="menu"
            >
              <button
                v-for="item in editMenuItems"
                :key="item.id"
                type="button"
                class="flex w-full items-center px-3 py-1.5 text-left text-sm transition-colors"
                :class="
                  item.id === 'undo' && !props.undoEnabled
                    ? 'cursor-not-allowed text-app-subtle'
                    : 'text-app-foreground hover:bg-app-accent'
                "
                role="menuitem"
                :aria-disabled="item.id === 'undo' && !props.undoEnabled"
                @click="onEditAction(item.id)"
              >
                <span>{{ item.label }}</span>
                <span
                  v-if="'shortcut' in item && item.shortcut"
                  class="ml-auto pl-4 text-xs text-app-subtle"
                >
                  {{ undoShortcutLabel }}
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </nav>

    <div class="flex items-center gap-1" :class="{ 'app-no-drag': isDesktop }">
      <button
        type="button"
        class="inline-flex h-8 items-center gap-1 rounded-md px-1.5 text-app-muted transition-colors hover:bg-app-accent hover:text-app-foreground"
        :aria-label="props.sidebarVisible ? t('menu.hideSidebar') : t('menu.showSidebar')"
        :aria-pressed="props.sidebarVisible"
        @click="emit('toggleSidebar')"
      >
        <PanelLeftClose v-if="props.sidebarVisible" :size="16" :stroke-width="1.75" />
        <PanelLeft v-else :size="16" :stroke-width="1.75" />
        <kbd :class="shortcutBadgeClass">{{ leftSidebarShortcutLabel }}</kbd>
      </button>

      <button
        type="button"
        class="inline-flex h-8 items-center gap-1 rounded-md px-1.5 text-app-muted transition-colors hover:bg-app-accent hover:text-app-foreground"
        :aria-label="props.rightSidebarVisible ? t('menu.hideEditorPanel') : t('menu.showEditorPanel')"
        :aria-pressed="props.rightSidebarVisible"
        @click="emit('toggleRightSidebar')"
      >
        <PanelRightClose v-if="props.rightSidebarVisible" :size="16" :stroke-width="1.75" />
        <PanelRight v-else :size="16" :stroke-width="1.75" />
        <kbd :class="shortcutBadgeClass">{{ rightSidebarShortcutLabel }}</kbd>
      </button>

      <a
        :href="GITHUB_URL"
        target="_blank"
        rel="noopener noreferrer"
        class="inline-flex h-8 items-center gap-1.5 rounded-md px-1.5 text-app-muted transition-colors hover:bg-app-accent hover:text-app-foreground"
        :aria-label="t('common.github')"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="currentColor"
          aria-hidden="true"
          class="shrink-0"
        >
          <path
            d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"
          />
        </svg>
        <span class="text-sm">{{ t('common.github') }}</span>
      </a>

      <button
        type="button"
        class="inline-flex size-8 shrink-0 items-center justify-center rounded-md text-app-muted transition-colors hover:bg-app-accent hover:text-app-foreground"
        :aria-label="t('menu.settings')"
        @click="emit('settingsClick')"
      >
        <Settings :size="16" :stroke-width="1.75" />
      </button>

      <!-- ── Window controls (Windows / Linux only) ── -->
      <template v-if="isWinLinuxDesktop">
        <div class="mx-0.5 h-5 w-px bg-app-border/60" />
        <div class="-mr-3 flex h-10 items-stretch">
          <button
            type="button"
            class="win-ctrl-btn group flex w-11 items-center justify-center text-app-muted transition-colors hover:bg-app-accent"
            :aria-label="t('menu.minimize')"
            @click="minimizeWindow"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <path d="M2 6h8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
            </svg>
          </button>
          <button
            type="button"
            class="win-ctrl-btn group flex w-11 items-center justify-center text-app-muted transition-colors hover:bg-app-accent"
            :aria-label="isWindowMaximized ? t('menu.restore') : t('menu.maximize')"
            @click="maximizeWindow"
          >
            <svg
              v-if="isWindowMaximized"
              width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"
            >
              <rect x="2.5" y="4.5" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.1" />
              <path d="M4.5 4.5V3.5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-1" stroke="currentColor" stroke-width="1.1" />
            </svg>
            <svg
              v-else
              width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"
            >
              <rect x="2" y="2" width="8" height="8" rx="1.2" stroke="currentColor" stroke-width="1.1" />
            </svg>
          </button>
          <button
            type="button"
            class="win-ctrl-btn group flex w-11 items-center justify-center text-app-muted transition-colors hover:bg-red-500 hover:text-white"
            :aria-label="t('menu.close')"
            @click="closeWindow"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
            </svg>
          </button>
        </div>
      </template>
    </div>
  </header>
</template>

<style scoped>
.app-drag {
  -webkit-app-region: drag;
}
.app-no-drag {
  -webkit-app-region: no-drag;
}
.app-no-drag::before,
.app-no-drag::after {
  -webkit-app-region: no-drag;
}
.win-ctrl-btn {
  -webkit-app-region: no-drag;
}
</style>

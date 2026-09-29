<script setup lang="ts">
import { ImageIcon, Trash2 } from '@lucide/vue'
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  getDisplayWorkspaceTitle,
  loadSavedProjectsFromLocalStorage,
  savedWorkspacesRevision,
} from '@/lib/workspace-storage'
import type { Workspace } from '@/types/workspace'

const { t, locale } = useI18n()

defineProps<{
  activeWorkspaceId: string
}>()

const emit = defineEmits<{
  select: [workspaceId: string]
  delete: [workspaceId: string]
}>()

const savedProjects = ref<Workspace[]>([])
const pendingDeleteId = ref<string | null>(null)

function refreshProjects(): void {
  savedProjects.value = loadSavedProjectsFromLocalStorage()
}

watch(savedWorkspacesRevision, refreshProjects)

onMounted(() => {
  refreshProjects()
})

onUnmounted(() => {})

function formatUpdatedAt(timestamp: number): string {
  return new Date(timestamp).toLocaleString(locale.value, {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function requestDelete(workspaceId: string): void {
  pendingDeleteId.value = workspaceId
}

function cancelDelete(): void {
  pendingDeleteId.value = null
}

function confirmDelete(workspaceId: string): void {
  pendingDeleteId.value = null
  emit('delete', workspaceId)
}
</script>

<template>
  <aside
    class="flex w-56 shrink-0 flex-col border-r border-app-border bg-app"
    :aria-label="t('sidebar.savedProjects')"
  >
    <div class="border-b border-app-border px-3 py-2.5">
      <h2 class="text-xs font-medium tracking-wide text-app-muted uppercase">{{ t('sidebar.projects') }}</h2>
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto p-2">
      <p v-if="savedProjects.length === 0" class="px-2 py-6 text-center text-xs text-app-subtle">
        {{ t('sidebar.noSavedProjects') }}
      </p>

      <ul v-else class="space-y-1">
        <li v-for="project in savedProjects" :key="project.id" class="relative">
          <button
            type="button"
            class="flex w-full items-start gap-2.5 rounded-lg px-2 py-2 pr-9 text-left transition-colors"
            :class="
              project.id === activeWorkspaceId
                ? 'bg-app-accent text-app-foreground'
                : 'text-app-muted hover:bg-app-accent hover:text-app-foreground'
            "
            @click="emit('select', project.id)"
          >
            <div
              class="mt-0.5 flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-md border border-app-border bg-app-elevated"
            >
              <ImageIcon
                v-if="project.hasSourceImage"
                :size="14"
                :stroke-width="1.75"
                class="text-app-subtle"
              />
            </div>

            <div class="min-w-0 flex-1">
              <p class="truncate text-sm leading-snug">{{ getDisplayWorkspaceTitle(project.title) }}</p>
              <p class="mt-0.5 text-xs text-app-subtle">{{ formatUpdatedAt(project.updatedAt) }}</p>
            </div>
          </button>

          <button
            type="button"
            class="absolute top-2 right-2 inline-flex size-7 items-center justify-center rounded-md text-app-subtle transition-colors hover:bg-app hover:text-red-600 dark:hover:text-red-400"
            :aria-label="t('sidebar.deleteProject', { title: getDisplayWorkspaceTitle(project.title) })"
            @click.stop="requestDelete(project.id)"
          >
            <Trash2 :size="14" :stroke-width="1.75" />
          </button>

          <div
            v-if="pendingDeleteId === project.id"
            class="absolute inset-0 z-10 flex flex-col justify-center gap-2 rounded-lg border border-app-border bg-app-elevated/95 p-2 shadow-sm backdrop-blur-sm"
          >
            <p class="px-1 text-xs text-app-foreground">
              {{ t('sidebar.confirmDelete', { title: getDisplayWorkspaceTitle(project.title) }) }}
            </p>
            <div class="flex gap-2">
              <button
                type="button"
                class="flex-1 rounded-md border border-app-border px-2 py-1 text-xs text-app-muted transition hover:bg-app-accent"
                @click.stop="cancelDelete"
              >
                {{ t('common.cancel') }}
              </button>
              <button
                type="button"
                class="flex-1 rounded-md bg-red-600 px-2 py-1 text-xs text-white transition hover:opacity-90"
                @click.stop="confirmDelete(project.id)"
              >
                {{ t('common.delete') }}
              </button>
            </div>
          </div>
        </li>
      </ul>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { X } from '@lucide/vue'
import { useI18n } from 'vue-i18n'

import type { WorkspaceTabItem } from '@/types/workspace'

const { t } = useI18n()

defineProps<{
  tabs: WorkspaceTabItem[]
  activeTabId: string
}>()

const emit = defineEmits<{
  select: [workspaceId: string]
  close: [workspaceId: string]
}>()
</script>

<template>
  <div class="app-tabbar" role="tablist">
    <div
      v-for="tab in tabs"
      :key="tab.id"
      role="tab"
      class="app-tab"
      :class="tab.id === activeTabId ? 'app-tab-active' : 'app-tab-inactive'"
      :aria-selected="tab.id === activeTabId"
    >
      <button
        type="button"
        class="flex min-w-0 items-center gap-1 truncate text-sm leading-none"
        @click="emit('select', tab.id)"
      >
        <span class="truncate">{{ tab.title }}</span>
        <span
          v-if="tab.isDirty"
          class="shrink-0 text-app-subtle"
          :aria-label="t('tab.unsavedChanges')"
          :title="t('tab.unsavedChanges')"
        >
          •
        </span>
      </button>
      <button
        type="button"
        class="inline-flex size-5 shrink-0 items-center justify-center rounded text-app-subtle transition-colors hover:bg-app-accent hover:text-app-foreground"
        :aria-label="t('tab.closeTab')"
        @click.stop="emit('close', tab.id)"
      >
        <X :size="12" :stroke-width="2" />
      </button>
    </div>
  </div>
</template>

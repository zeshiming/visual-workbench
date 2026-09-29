<script setup lang="ts">
import { Images, Palette, SlidersHorizontal, Sparkles, WandSparkles } from '@lucide/vue'
import type { WorkspaceMode } from '@/types/workspace-mode'

export type { WorkspaceMode }

defineProps<{
  activeMode: WorkspaceMode
}>()

const emit = defineEmits<{
  select: [mode: WorkspaceMode]
}>()

const items: Array<{
  id: WorkspaceMode
  label: string
  index: string
  icon: typeof Images
  enabled: boolean
}> = [
  { id: 'photos', label: '照片', index: '01', icon: Images, enabled: true },
  { id: 'develop', label: '调色', index: '02', icon: SlidersHorizontal, enabled: true },
  { id: 'match', label: '追色', index: '03', icon: Palette, enabled: true },
  { id: 'fill', label: '生成填充', index: '04', icon: WandSparkles, enabled: false },
  { id: 'styles', label: '风格化', index: '05', icon: Sparkles, enabled: true },
  { id: 'ai', label: 'AI 修图', index: '06', icon: WandSparkles, enabled: true },
]
</script>

<template>
  <nav class="app-tool-rail" aria-label="工作流">
    <button
      v-for="item in items"
      :key="item.id"
      type="button"
      class="app-tool-rail-item"
      :class="{
        'app-tool-rail-item-active': activeMode === item.id,
        'app-tool-rail-item-disabled': !item.enabled,
      }"
      :disabled="!item.enabled"
      :aria-current="activeMode === item.id ? 'page' : undefined"
      :title="item.enabled ? item.label : `${item.label}（尚未接入）`"
      @click="emit('select', item.id)"
    >
      <component :is="item.icon" :size="16" :stroke-width="1.7" />
      <span class="app-tool-rail-index">{{ item.index }}</span>
      <span class="app-tool-rail-label">{{ item.label }}</span>
    </button>
  </nav>
</template>

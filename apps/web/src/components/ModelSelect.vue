<script setup lang="ts">
import { Check, ChevronDown } from '@lucide/vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatModelLabel } from '@/lib/app-settings'
import type { AppSettings, ModelEntry } from '@/types/app-settings'

const { t } = useI18n()

const props = defineProps<{
  settings: AppSettings
  models: ModelEntry[]
  modelValue: string
  disabled?: boolean
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const open = ref(false)
const rootRef = ref<HTMLElement | null>(null)

const triggerClass = 'app-select-trigger'

const options = computed(() =>
  props.models.map((model) => ({
    value: model.id,
    label: formatModelLabel(props.settings, model),
  })),
)

const isDisabled = computed(() => props.disabled || props.models.length === 0)

const selectedLabel = computed(() => {
  const selected = options.value.find((option) => option.value === props.modelValue)
  if (selected) {
    return selected.label
  }

  if (props.models.length === 0) {
    return t('settings.addModelsFirst')
  }

  return props.placeholder ?? t('settings.selectModel')
})

function toggleOpen(): void {
  if (isDisabled.value) {
    return
  }

  open.value = !open.value
}

function selectOption(value: string): void {
  emit('update:modelValue', value)
  open.value = false
}

function onDocumentPointerDown(event: PointerEvent): void {
  const target = event.target as Node

  if (open.value && !rootRef.value?.contains(target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('pointerdown', onDocumentPointerDown))
onUnmounted(() => document.removeEventListener('pointerdown', onDocumentPointerDown))
</script>

<template>
  <div ref="rootRef" class="relative">
    <button
      type="button"
      :class="triggerClass"
      :disabled="isDisabled"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click.stop="toggleOpen"
    >
      <span class="min-w-0 flex-1 truncate">{{ selectedLabel }}</span>
      <ChevronDown
        :size="14"
        :stroke-width="1.75"
        class="shrink-0 text-app-subtle transition-transform"
        :class="open ? 'rotate-180' : ''"
      />
    </button>

    <div
      v-if="open && !isDisabled"
      class="absolute left-0 right-0 top-full z-50 pt-1"
      @pointerdown.stop
    >
      <ul
        role="listbox"
        class="max-h-48 overflow-y-auto rounded-lg border border-app-border bg-app-elevated py-1 shadow-lg shadow-black/10"
      >
        <li v-for="option in options" :key="option.value" role="presentation">
          <button
            type="button"
            role="option"
            class="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm transition-colors"
            :class="
              modelValue === option.value
                ? 'bg-app-accent text-app-foreground'
                : 'text-app-foreground hover:bg-app-accent'
            "
            :aria-selected="modelValue === option.value"
            @click="selectOption(option.value)"
          >
            <Check
              v-if="modelValue === option.value"
              :size="14"
              :stroke-width="2"
              class="shrink-0 text-app-muted"
            />
            <span v-else class="inline-block w-3.5 shrink-0" aria-hidden="true" />
            <span class="min-w-0 truncate">{{ option.label }}</span>
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>

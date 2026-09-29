<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  open: boolean
  initialName: string
  errorMessage?: string
  saving?: boolean
}>()

const emit = defineEmits<{
  confirm: [name: string]
  cancel: []
}>()

const name = ref('')
const validationError = ref('')
const inputRef = ref<HTMLInputElement | null>(null)

const inputClass = 'app-field'

watch(
  () => [props.open, props.initialName] as const,
  async ([isOpen, initialName]) => {
    if (!isOpen) {
      return
    }

    name.value = initialName
    validationError.value = ''
    await nextTick()
    inputRef.value?.focus()
    inputRef.value?.select()
  },
)

function readName(): string {
  return (inputRef.value?.value ?? name.value).trim()
}

function handleSubmit(): void {
  if (props.saving) {
    return
  }

  validationError.value = ''

  const trimmed = readName()
  if (!trimmed) {
    validationError.value = t('saveDialog.nameRequired')
    inputRef.value?.focus()
    return
  }

  name.value = trimmed
  emit('confirm', trimmed)
}

function handleCancel(): void {
  emit('cancel')
}

function onBackdropClick(): void {
  handleCancel()
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-100 flex items-center justify-center bg-black/40 p-4 backdrop-blur-[1px]"
      @click.self="onBackdropClick"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="save-workspace-title"
        class="w-full max-w-sm rounded-xl border border-app-border bg-app-elevated p-5 shadow-xl shadow-black/10"
      >
        <h2 id="save-workspace-title" class="text-base font-semibold text-app-foreground">
          {{ t('saveDialog.title') }}
        </h2>
        <p class="mt-1 text-sm text-app-muted">{{ t('saveDialog.description') }}</p>

        <div class="mt-4 space-y-4">
          <label class="block space-y-1.5">
            <span class="text-sm font-medium text-app-foreground">{{ t('common.name') }}</span>
            <input
              ref="inputRef"
              v-model="name"
              type="text"
              autocomplete="off"
              :placeholder="t('saveDialog.namePlaceholder')"
              :class="inputClass"
              @input="validationError = ''"
              @keydown.enter.prevent="handleSubmit"
            />
            <p v-if="validationError" class="text-xs text-red-600 dark:text-red-400">
              {{ validationError }}
            </p>
            <p v-else-if="errorMessage" class="text-xs text-red-600 dark:text-red-400">
              {{ errorMessage }}
            </p>
          </label>

          <div class="flex justify-end gap-2 pt-1">
            <button
              type="button"
              class="rounded-lg px-3 py-2 text-sm text-app-muted transition-colors hover:bg-app-accent hover:text-app-foreground"
              @click="handleCancel"
            >
              {{ t('common.cancel') }}
            </button>
            <button
              type="button"
              class="app-btn-primary px-4 disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="props.saving"
              @click="handleSubmit"
            >
              {{ props.saving ? t('common.saving') : t('common.save') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

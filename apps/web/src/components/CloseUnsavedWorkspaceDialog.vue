<script setup lang="ts">
import { useI18n } from 'vue-i18n'

defineProps<{
  open: boolean
  workspaceTitle: string
}>()

const emit = defineEmits<{
  save: []
  discard: []
  cancel: []
}>()

const { t } = useI18n()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-100 flex items-center justify-center bg-black/40 p-4 backdrop-blur-[1px]"
      @click.self="emit('cancel')"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="close-unsaved-workspace-title"
        class="w-full max-w-sm rounded-xl border border-app-border bg-app-elevated p-5 shadow-xl shadow-black/10"
      >
        <h2 id="close-unsaved-workspace-title" class="text-base font-semibold text-app-foreground">
          {{ t('closeDialog.title') }}
        </h2>
        <p class="mt-2 text-sm text-app-muted">
          {{ t('closeDialog.message', { title: workspaceTitle }) }}
        </p>

        <div class="mt-5 flex justify-end gap-2">
          <button
            type="button"
            class="rounded-lg px-3 py-2 text-sm text-app-muted transition-colors hover:bg-app-accent hover:text-app-foreground"
            @click="emit('cancel')"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            type="button"
            class="rounded-lg px-3 py-2 text-sm text-app-muted transition-colors hover:bg-app-accent hover:text-app-foreground"
            @click="emit('discard')"
          >
            {{ t('closeDialog.discard') }}
          </button>
          <button
            type="button"
            class="app-btn-primary px-4"
            @click="emit('save')"
          >
            {{ t('common.save') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

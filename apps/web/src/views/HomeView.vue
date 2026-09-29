<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <section class="flex flex-1 items-center justify-center bg-app-surface p-6 text-sm text-app-muted">
    {{ t('home.mainWorkspace') }}
  </section>
</template>

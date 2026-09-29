<script setup lang="ts">
import { ChevronDown, Plus, Trash2 } from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { createId, getProviderDefinition, listModelsByRole } from '@/lib/app-settings'
import { initAppSettings, loadAppSettings, saveAppSettings, clearAppSettings } from '@/lib/config-storage'
import { clearBackendSettings } from '@/lib/api-client'
import ModelSelect from '@/components/ModelSelect.vue'
import { type AppLocale, setLocale, SUPPORTED_LOCALES } from '@/i18n'
import { loadLocale, saveLocale } from '@/lib/locale-storage'
import { PROVIDER_KINDS } from '@/lib/model-providers'
import { type Theme, applyTheme, loadTheme, saveTheme } from '@/lib/theme-storage'
import type { AppSettings, ModelEntry, ModelRole, ProviderKind } from '@/types/app-settings'

const { t } = useI18n()

const form = ref<AppSettings>({
  providers: [],
  models: [],
  defaultAnalysisModelId: '',
  defaultEditModelId: '',
})

const theme = ref<Theme>('light')
const locale = ref<AppLocale>(loadLocale())
const loading = ref(true)
const saving = ref(false)
const clearing = ref(false)
const error = ref('')
const saved = ref(false)
const clearConfirm = ref(false)

const themeOptions = computed(() => [
  { value: 'light' as const, label: t('theme.light') },
  { value: 'dark' as const, label: t('theme.dark') },
])

const localeOptions = computed(() =>
  SUPPORTED_LOCALES.map((value) => ({
    value,
    label: t(`locale.${value}`),
  })),
)

const analysisModels = computed(() => listModelsByRole(form.value, 'analysis'))
const editModels = computed(() => listModelsByRole(form.value, 'edit'))

const inputClass = 'app-field'

const roleOptions = computed(() => [
  { value: 'analysis' as const, label: t('roles.analysis') },
  { value: 'edit' as const, label: t('roles.edit') },
])

const expandedProviders = reactive<Record<ProviderKind, boolean>>({
  openrouter: true,
  gemini: false,
  'openai-compatible': false,
})

function isProviderExpanded(kind: ProviderKind): boolean {
  return expandedProviders[kind]
}

function toggleProviderExpanded(kind: ProviderKind): void {
  expandedProviders[kind] = !expandedProviders[kind]
}

function syncProviderExpandedState(settings: AppSettings): void {
  for (const kind of PROVIDER_KINDS) {
    const provider = settings.providers.find((item) => item.id === kind)
    const modelCount = settings.models.filter((model) => model.providerId === kind).length
    const hasContent = Boolean(provider?.key.trim()) || modelCount > 0

    if (hasContent) {
      expandedProviders[kind] = true
    }
  }
}

onMounted(async () => {
  form.value = await initAppSettings()
  syncProviderExpandedState(form.value)
  theme.value = loadTheme()
  locale.value = loadLocale()
  loading.value = false
})

function setTheme(nextTheme: Theme) {
  theme.value = nextTheme
  saveTheme(nextTheme)
  applyTheme(nextTheme)
}

function setAppLocale(nextLocale: AppLocale) {
  locale.value = nextLocale
  setLocale(nextLocale)
}

function providerDef(kind: ProviderKind) {
  return getProviderDefinition(kind)
}

function addModel(providerId: ProviderKind) {
  const id = createId()
  form.value.models.push({
    id,
    providerId,
    modelId: '',
    label: '',
    roles: ['edit'],
  })
  expandedProviders[providerId] = true
}

function providerSummary(kind: ProviderKind): string {
  const modelCount = modelsForProvider(kind).length
  const hasKey = Boolean(form.value.providers.find((provider) => provider.id === kind)?.key.trim())

  if (modelCount > 0 && hasKey) {
    return t('settings.providerSummary.modelsWithKey', { count: modelCount })
  }

  if (modelCount > 0) {
    return t('settings.providerSummary.models', { count: modelCount })
  }

  if (hasKey) {
    return t('settings.providerSummary.keyConfigured')
  }

  return t('settings.providerSummary.notConfigured')
}

function removeModel(modelId: string) {
  form.value.models = form.value.models.filter((model) => model.id !== modelId)

  if (form.value.defaultAnalysisModelId === modelId) {
    form.value.defaultAnalysisModelId = analysisModels.value[0]?.id ?? ''
  }

  if (form.value.defaultEditModelId === modelId) {
    form.value.defaultEditModelId = editModels.value[0]?.id ?? ''
  }
}

function toggleModelRole(model: ModelEntry, role: ModelRole) {
  if (model.roles.includes(role)) {
    model.roles = model.roles.filter((item) => item !== role)
    return
  }

  model.roles = [...model.roles, role]
}

function modelsForProvider(providerId: ProviderKind): ModelEntry[] {
  return form.value.models.filter((model) => model.providerId === providerId)
}

async function handleSubmit() {
  saving.value = true
  error.value = ''
  saved.value = false

  try {
    form.value = await saveAppSettings(form.value)
    saved.value = true
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('settings.saveFailed')
  } finally {
    saving.value = false
  }
}

async function handleClearSettings() {
  if (!clearConfirm.value) {
    clearConfirm.value = true
    return
  }

  clearing.value = true
  error.value = ''
  saved.value = false

  try {
    // Clear backend settings
    await clearBackendSettings()

    // Reset cache and form to defaults
    form.value = await clearAppSettings()
    theme.value = loadTheme()
    locale.value = loadLocale()
    syncProviderExpandedState(form.value)

    clearConfirm.value = false
    saved.value = true
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('settings.clearFailed')
  } finally {
    clearing.value = false
  }
}

function cancelClear() {
  clearConfirm.value = false
}
</script>

<template>
  <section class="mx-auto w-full max-w-2xl p-6">
    <div v-if="loading" class="flex items-center justify-center py-20">
      <p class="text-sm text-app-muted">{{ t('common.loading') }}</p>
    </div>

    <template v-else>
      <div class="mb-6">
        <h1 class="text-lg font-semibold text-app-foreground">{{ t('settings.title') }}</h1>
        <p class="mt-1 text-sm text-app-muted">
          {{ t('settings.description') }}
        </p>
      </div>

      <section class="mb-8 space-y-3">
        <div>
          <h2 class="text-sm font-medium text-app-foreground">{{ t('locale.title') }}</h2>
          <p class="mt-1 text-xs text-app-subtle">{{ t('locale.description') }}</p>
        </div>

        <div
          class="inline-flex flex-wrap gap-1 rounded-lg border border-app-border bg-app-accent p-1"
          role="radiogroup"
          :aria-label="t('locale.title')"
        >
          <button
            v-for="option in localeOptions"
            :key="option.value"
            type="button"
            role="radio"
            class="rounded-md px-4 py-1.5 text-sm transition-colors"
            :class="
              locale === option.value
                ? 'bg-app-elevated text-app-foreground shadow-sm'
                : 'text-app-muted hover:text-app-foreground'
            "
            :aria-checked="locale === option.value"
            @click="setAppLocale(option.value)"
          >
            {{ option.label }}
          </button>
        </div>
      </section>

      <section class="mb-8 space-y-3">
        <div>
          <h2 class="text-sm font-medium text-app-foreground">{{ t('theme.title') }}</h2>
          <p class="mt-1 text-xs text-app-subtle">{{ t('theme.description') }}</p>
        </div>

        <div
          class="inline-flex rounded-lg border border-app-border bg-app-accent p-1"
          role="radiogroup"
          :aria-label="t('theme.label')"
        >
          <button
            v-for="option in themeOptions"
            :key="option.value"
            type="button"
            role="radio"
            class="rounded-md px-4 py-1.5 text-sm transition-colors"
            :class="
              theme === option.value
                ? 'bg-app-elevated text-app-foreground shadow-sm'
                : 'text-app-muted hover:text-app-foreground'
            "
            :aria-checked="theme === option.value"
            @click="setTheme(option.value)"
          >
            {{ option.label }}
          </button>
        </div>
      </section>

      <form class="space-y-8" @submit.prevent="handleSubmit">
        <section class="space-y-4">
          <div>
            <h2 class="text-sm font-medium text-app-foreground">{{ t('settings.providers') }}</h2>
            <p class="mt-1 text-xs text-app-subtle">
              {{ t('settings.providersHint') }}
            </p>
          </div>

          <div
            v-for="provider in form.providers"
            :key="provider.id"
            class="overflow-hidden rounded-xl border border-app-border bg-app-accent/40"
          >
            <button
              type="button"
              class="flex w-full items-center gap-2 px-4 py-3 text-left transition hover:bg-app-accent/80"
              :aria-expanded="isProviderExpanded(provider.id)"
              @click="toggleProviderExpanded(provider.id)"
            >
              <ChevronDown
                :size="16"
                :stroke-width="1.75"
                class="shrink-0 text-app-muted transition-transform"
                :class="isProviderExpanded(provider.id) ? 'rotate-0' : '-rotate-90'"
              />
              <span class="min-w-0 flex-1">
                <span class="block text-sm font-medium text-app-foreground">
                  {{ providerDef(provider.id).name }}
                </span>
                <span class="mt-0.5 block text-xs text-app-subtle">
                  {{ providerSummary(provider.id) }}
                </span>
              </span>
            </button>

            <div v-show="isProviderExpanded(provider.id)" class="space-y-4 border-t border-app-border px-4 py-4">
            <div class="grid gap-4">
              <label class="block space-y-1.5">
                <span class="text-xs font-medium text-app-muted">{{ t('settings.apiHost') }}</span>
                <input
                  v-model="provider.host"
                  type="url"
                  required
                  autocomplete="off"
                  :readonly="!providerDef(provider.id).hostEditable"
                  :placeholder="providerDef(provider.id).defaultHost"
                  :class="[
                    inputClass,
                    !providerDef(provider.id).hostEditable ? 'cursor-default opacity-80' : '',
                  ]"
                />
                <span class="text-xs text-app-subtle">{{ providerDef(provider.id).hostHint }}</span>
              </label>

              <label class="block space-y-1.5">
                <span class="text-xs font-medium text-app-muted">{{ t('settings.apiKey') }}</span>
                <input
                  v-model="provider.key"
                  type="password"
                  autocomplete="off"
                  :placeholder="providerDef(provider.id).keyPlaceholder"
                  :class="inputClass"
                />
                <span class="text-xs text-app-subtle">{{ t('settings.keyServerHint') }}</span>
              </label>
            </div>

            <div class="space-y-3 border-t border-app-border pt-4">
              <div class="flex items-center justify-between gap-3">
                <h4 class="text-xs font-medium text-app-muted uppercase">{{ t('settings.modelList') }}</h4>
                <button
                  type="button"
                  class="inline-flex items-center gap-1 rounded-md border border-app-border px-2 py-1 text-[11px] font-medium text-app-foreground transition hover:bg-app-elevated"
                  @click.stop="addModel(provider.id)"
                >
                  <Plus :size="12" :stroke-width="1.75" />
                  {{ t('settings.addModel') }}
                </button>
              </div>

              <p
                v-if="modelsForProvider(provider.id).length === 0"
                class="rounded-lg border border-dashed border-app-border px-3 py-3 text-center text-xs text-app-subtle"
              >
                {{ t('settings.noModelsYet') }}
              </p>

              <div
                v-for="model in modelsForProvider(provider.id)"
                :key="model.id"
                class="space-y-3 rounded-lg border border-app-border bg-app px-3 py-3"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="text-xs font-medium text-app-foreground">{{ t('common.model') }}</span>
                  <button
                    type="button"
                    class="rounded p-1 text-app-muted transition hover:bg-app-accent hover:text-red-600"
                    :aria-label="t('settings.deleteModel')"
                    @click="removeModel(model.id)"
                  >
                    <Trash2 :size="12" :stroke-width="1.75" />
                  </button>
                </div>

                <label class="block space-y-1">
                  <span class="text-xs text-app-muted">{{ t('settings.displayName') }}</span>
                  <input
                    v-model="model.label"
                    type="text"
                    required
                    :placeholder="t('settings.displayNamePlaceholder')"
                    :class="inputClass"
                  />
                </label>

                <label class="block space-y-1">
                  <span class="text-xs text-app-muted">{{ t('settings.modelId') }}</span>
                  <input
                    v-model="model.modelId"
                    type="text"
                    required
                    autocomplete="off"
                    :placeholder="providerDef(provider.id).modelIdPlaceholder"
                    :class="inputClass"
                  />
                </label>

                <div class="space-y-1.5">
                  <span class="text-xs text-app-muted">{{ t('settings.role') }}</span>
                  <div class="flex flex-wrap gap-2">
                    <label
                      v-for="roleOption in roleOptions"
                      :key="roleOption.value"
                      class="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-app-border px-2.5 py-1 text-xs transition"
                      :class="
                        model.roles.includes(roleOption.value)
                          ? 'bg-app-primary text-app-primary-foreground border-transparent'
                          : 'text-app-muted hover:bg-app-accent'
                      "
                    >
                      <input
                        type="checkbox"
                        class="sr-only"
                        :checked="model.roles.includes(roleOption.value)"
                        @change="toggleModelRole(model, roleOption.value)"
                      />
                      {{ roleOption.label }}
                    </label>
                  </div>
                  <p class="text-[11px] text-app-subtle">
                    {{ t('settings.roleHint') }}
                  </p>
                </div>
              </div>
            </div>
            </div>
          </div>
        </section>

        <section class="space-y-4 rounded-xl border border-app-border p-4">
          <div>
            <h2 class="text-sm font-medium text-app-foreground">{{ t('settings.defaultModels') }}</h2>
            <p class="mt-1 text-xs text-app-subtle">{{ t('settings.defaultModelsHint') }}</p>
          </div>

          <label class="block space-y-1.5">
            <span class="text-sm font-medium text-app-foreground">{{ t('settings.defaultAnalysisModel') }}</span>
            <ModelSelect
              v-model="form.defaultAnalysisModelId"
              :settings="form"
              :models="analysisModels"
              :placeholder="t('settings.selectAnalysisModel')"
            />
          </label>

          <label class="block space-y-1.5">
            <span class="text-sm font-medium text-app-foreground">{{ t('settings.defaultEditModel') }}</span>
            <ModelSelect
              v-model="form.defaultEditModelId"
              :settings="form"
              :models="editModels"
              :placeholder="t('settings.selectEditModel')"
            />
          </label>
        </section>

        <div class="space-y-4">
          <div class="flex items-center gap-3">
            <button
              type="submit"
              :disabled="saving"
              class="app-btn-primary px-4 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {{ saving ? t('common.saving') : t('common.save') }}
            </button>

            <p v-if="saved" class="text-sm text-emerald-600 dark:text-emerald-400">{{ t('common.saved') }}</p>
            <p v-else-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
          </div>

          <div class="border-t border-app-border pt-4">
            <div class="flex flex-wrap items-center gap-3">
              <button
                v-if="!clearConfirm"
                type="button"
                class="rounded-lg border border-red-300 px-4 py-1.5 text-sm text-red-600 transition hover:bg-red-50 dark:border-red-700 dark:text-red-400 dark:hover:bg-red-950"
                @click="handleClearSettings"
              >
                {{ t('settings.clearAll') }}
              </button>

              <template v-else>
                <span class="text-sm text-red-600 dark:text-red-400">
                  {{ t('settings.clearConfirm') }}
                </span>
                <button
                  type="button"
                  :disabled="clearing"
                  class="rounded-lg bg-red-600 px-4 py-1.5 text-sm text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60"
                  @click="handleClearSettings"
                >
                  {{ clearing ? t('common.processing') : t('common.confirm') }}
                </button>
                <button
                  type="button"
                  :disabled="clearing"
                  class="rounded-lg border border-app-border px-4 py-1.5 text-sm text-app-muted transition hover:bg-app-accent"
                  @click="cancelClear"
                >
                  {{ t('common.cancel') }}
                </button>
              </template>
            </div>
          </div>
        </div>
      </form>
    </template>
  </section>
</template>

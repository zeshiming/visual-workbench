import { translate } from '@/i18n'

import {
  createDefaultProviders,
  getProviderDefinition,
  getProviderLabel,
  inferProviderKind,
  isProviderKind,
} from '@/lib/model-providers'
import type { AppSettings, ModelEntry, ModelProvider, ModelRole, ModelSelection, ProviderKind } from '@/types/app-settings'

// Local Config type (no @doushabao/core dependency)
interface ModelEndpoint {
  host: string
  key: string
  model: string
}

interface Config {
  analysis: ModelEndpoint
  edit: ModelEndpoint
}

export function createId(): string {
  return crypto.randomUUID()
}

export function emptyAppSettings(): AppSettings {
  return {
    providers: createDefaultProviders(),
    models: [],
    defaultAnalysisModelId: '',
    defaultEditModelId: '',
  }
}

export function normalizeAppSettings(settings: AppSettings): AppSettings {
  const normalized = emptyAppSettings()

  for (const stored of settings.providers) {
    const kind = inferProviderKind(stored)
    const target = normalized.providers.find((provider) => provider.id === kind)

    if (!target) {
      continue
    }

    if (stored.key.trim()) {
      target.key = stored.key.trim()
    }

    if (kind === 'openai-compatible' && stored.host?.trim()) {
      target.host = stored.host.trim()
    }
  }

  const providerIdMap = new Map<string, ProviderKind>()

  for (const stored of settings.providers) {
    providerIdMap.set(stored.id, inferProviderKind(stored))
  }

  const models: ModelEntry[] = settings.models
    .map((model) => {
      const mappedKind = providerIdMap.get(model.providerId)
      const providerId: ProviderKind =
        mappedKind ?? (isProviderKind(model.providerId) ? model.providerId : 'openrouter')

      return {
        ...model,
        providerId,
      }
    })
    .filter((model) => isProviderKind(model.providerId))

  return {
    providers: normalized.providers,
    models,
    defaultAnalysisModelId: settings.defaultAnalysisModelId ?? '',
    defaultEditModelId: settings.defaultEditModelId ?? '',
  }
}

export function getProvider(settings: AppSettings, providerId: ProviderKind): ModelProvider | undefined {
  return settings.providers.find((provider) => provider.id === providerId)
}

export function getModelEntry(settings: AppSettings, modelId: string): ModelEntry | undefined {
  return settings.models.find((model) => model.id === modelId)
}

export function listModelsByRole(settings: AppSettings, role: ModelRole): ModelEntry[] {
  return settings.models.filter((model) => model.roles.includes(role))
}

export function formatModelLabel(settings: AppSettings, model: ModelEntry): string {
  const modelLabel = model.label.trim() || model.modelId.trim() || translate('common.unnamedModel')

  return `${getProviderLabel(model.providerId)} · ${modelLabel}`
}

export function resolveModelId(
  settings: AppSettings,
  role: ModelRole,
  selection?: ModelSelection,
): string {
  const selected =
    role === 'analysis' ? selection?.analysisModelId : selection?.editModelId

  if (selected) {
    return selected
  }

  return role === 'analysis' ? settings.defaultAnalysisModelId : settings.defaultEditModelId
}

export function resolveRunConfig(
  settings: AppSettings,
  selection?: ModelSelection,
): Config | null {
  const analysisModelId = resolveModelId(settings, 'analysis', selection)
  const editModelId = resolveModelId(settings, 'edit', selection)

  const analysisModel = getModelEntry(settings, analysisModelId)
  const editModel = getModelEntry(settings, editModelId)

  if (!analysisModel || !editModel) {
    return null
  }

  const analysisProvider = getProvider(settings, analysisModel.providerId)
  const editProvider = getProvider(settings, editModel.providerId)

  if (!analysisProvider || !editProvider) {
    return null
  }

  if (!analysisModel.roles.includes('analysis') || !editModel.roles.includes('edit')) {
    return null
  }

  return {
    analysis: {
      host: analysisProvider.host,
      key: analysisProvider.key,
      model: analysisModel.modelId,
    },
    edit: {
      host: editProvider.host,
      key: editProvider.key,
      model: editModel.modelId,
    },
  }
}

export function validateRunConfig(
  settings: AppSettings,
  selection?: ModelSelection,
): Config {
  const config = resolveRunConfig(settings, selection)

  if (!config) {
    throw new Error(translate('errors.configureModelsFirst'))
  }

  if (!config.analysis.host.trim() || !config.analysis.model.trim()) {
    throw new Error(`${translate('errors.analysisModelRequired')}：配置不完整`)
  }

  if (!config.edit.host.trim() || !config.edit.model.trim()) {
    throw new Error(`${translate('errors.editModelRequired')}：配置不完整`)
  }

  if (config.analysis.model === config.edit.model && config.analysis.host === config.edit.host) {
    throw new Error('分析模型与修图模型不能相同，修图模型需支持图像输出')
  }

  return config
}

export function validateAppSettings(settings: AppSettings): string | null {
  if (settings.providers.length !== 3) {
    return translate('errors.providersIncomplete')
  }

  for (const provider of settings.providers) {
    if (!isProviderKind(provider.id)) {
      return translate('errors.invalidProvider')
    }

    if (!provider.host.trim()) {
      return translate('errors.providerHostRequired', { provider: getProviderLabel(provider.id) })
    }
  }

  if (settings.models.length === 0) {
    return translate('errors.addModelRequired')
  }

  for (const model of settings.models) {
    if (!model.modelId.trim() || !model.label.trim()) {
      return translate('errors.modelFieldsRequired')
    }

    if (model.roles.length === 0) {
      return translate('errors.modelRoleRequired')
    }

    if (!getProvider(settings, model.providerId)) {
      return translate('errors.orphanModel')
    }
  }

  const analysisModels = listModelsByRole(settings, 'analysis')
  const editModels = listModelsByRole(settings, 'edit')

  if (analysisModels.length === 0) {
    return translate('errors.analysisModelRequired')
  }

  if (editModels.length === 0) {
    return translate('errors.editModelRequired')
  }

  if (!settings.defaultAnalysisModelId || !getModelEntry(settings, settings.defaultAnalysisModelId)) {
    return translate('errors.defaultAnalysisRequired')
  }

  if (!settings.defaultEditModelId || !getModelEntry(settings, settings.defaultEditModelId)) {
    return translate('errors.defaultEditRequired')
  }

  const defaultAnalysis = getModelEntry(settings, settings.defaultAnalysisModelId)
  const defaultEdit = getModelEntry(settings, settings.defaultEditModelId)

  if (!defaultAnalysis?.roles.includes('analysis')) {
    return translate('errors.defaultAnalysisRole')
  }

  if (!defaultEdit?.roles.includes('edit')) {
    return translate('errors.defaultEditRole')
  }

  const usedProviderIds = new Set(settings.models.map((model) => model.providerId))

  for (const provider of settings.providers) {
    if (usedProviderIds.has(provider.id) && !provider.key.trim()) {
      return translate('errors.providerKeyRequired', { provider: getProviderLabel(provider.id) })
    }
  }

  return null
}

export function validateAndResolveDefaults(settings: AppSettings): AppSettings {
  const normalized = normalizeAppSettings(settings)
  const error = validateAppSettings(normalized)

  if (error) {
    throw new Error(error)
  }

  validateRunConfig(normalized)

  return normalized
}

export { getProviderDefinition, getProviderLabel }

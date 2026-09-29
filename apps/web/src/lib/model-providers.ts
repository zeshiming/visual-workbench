import type { ModelProvider, ProviderKind } from '@/types/app-settings'

import { translate } from '@/i18n'

export const PROVIDER_KINDS: ProviderKind[] = ['openrouter', 'gemini', 'openai-compatible']

export const DEFAULT_OPENROUTER_HOST = 'https://openrouter.ai/api/v1'

export const DEFAULT_GEMINI_HOST =
  'https://generativelanguage.googleapis.com/v1beta/openai/'

export const DEFAULT_OPENAI_COMPATIBLE_HOST = 'https://api.openai.com/v1'

export type ProviderDefinition = {
  id: ProviderKind
  name: string
  defaultHost: string
  hostEditable: boolean
  hostHint: string
  keyPlaceholder: string
  modelIdPlaceholder: string
}

export const PROVIDER_DEFINITIONS: Record<ProviderKind, ProviderDefinition> = {
  openrouter: {
    id: 'openrouter',
    name: 'OpenRouter',
    defaultHost: DEFAULT_OPENROUTER_HOST,
    hostEditable: false,
    hostHint: '官方 OpenRouter 端点，无需修改。',
    keyPlaceholder: 'sk-or-...',
    modelIdPlaceholder: 'google/gemini-2.5-flash-preview',
  },
  gemini: {
    id: 'gemini',
    name: 'Gemini',
    defaultHost: DEFAULT_GEMINI_HOST,
    hostEditable: false,
    hostHint: 'Google Gemini OpenAI 兼容端点，无需修改。',
    keyPlaceholder: 'AIza...',
    modelIdPlaceholder: 'gemini-2.5-flash',
  },
  'openai-compatible': {
    id: 'openai-compatible',
    name: 'OpenAI 兼容',
    defaultHost: DEFAULT_OPENAI_COMPATIBLE_HOST,
    hostEditable: true,
    hostHint: '任意 OpenAI Chat Completions 兼容 API（如 OpenAI、DeepSeek、本地代理等）。',
    keyPlaceholder: 'sk-...',
    modelIdPlaceholder: 'gpt-4o',
  },
}

export function isProviderKind(value: string): value is ProviderKind {
  return (PROVIDER_KINDS as string[]).includes(value)
}

export function getProviderDefinition(kind: ProviderKind): ProviderDefinition {
  const base = PROVIDER_DEFINITIONS[kind]
  const providerKey = kind === 'openai-compatible' ? 'openaiCompatible' : kind

  return {
    ...base,
    name: translate(`providers.${providerKey}.name`),
    hostHint: translate(`providers.${providerKey}.hostHint`),
  }
}

export function getProviderLabel(kind: ProviderKind): string {
  return getProviderDefinition(kind).name
}

export function createDefaultProviders(): ModelProvider[] {
  return PROVIDER_KINDS.map((kind) => ({
    id: kind,
    host: getProviderDefinition(kind).defaultHost,
    key: '',
  }))
}

type StoredProviderLike = {
  id: string
  name?: string
  host?: string
  key?: string
}

export function inferProviderKind(provider: StoredProviderLike): ProviderKind {
  if (isProviderKind(provider.id)) {
    return provider.id
  }

  const name = (provider.name ?? '').toLowerCase()
  const host = (provider.host ?? '').toLowerCase()

  if (name.includes('openrouter') || host.includes('openrouter.ai')) {
    return 'openrouter'
  }

  if (
    name.includes('gemini') ||
    host.includes('generativelanguage.googleapis.com') ||
    host.includes('googleapis.com')
  ) {
    return 'gemini'
  }

  return 'openai-compatible'
}

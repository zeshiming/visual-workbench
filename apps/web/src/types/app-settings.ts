export type ModelRole = 'analysis' | 'edit'

export type ProviderKind = 'openrouter' | 'gemini' | 'openai-compatible'

export type ModelProvider = {
  id: ProviderKind
  host: string
  key: string
}

export type ModelEntry = {
  id: string
  providerId: ProviderKind
  /** API model slug, e.g. google/gemini-2.5-flash-preview */
  modelId: string
  label: string
  roles: ModelRole[]
}

export type AppSettings = {
  providers: ModelProvider[]
  models: ModelEntry[]
  defaultAnalysisModelId: string
  defaultEditModelId: string
}

export type ModelSelection = {
  analysisModelId?: string | null
  editModelId?: string | null
}

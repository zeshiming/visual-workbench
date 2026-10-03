/**
 * Thin wrapper that bridges the workspace layer to the backend API.
 * No business logic — the Python backend handles everything.
 */
import { translate } from '@/i18n'

import { validateRunConfig } from '@/lib/app-settings'
import { previewAgentPlan, runAgentViaBackend, type ApiAgentRunOrigin, type AgentRunStep, type ApiAgentRunControls, type ApiAgentPlan, type ApiToolRunTrace } from '@/lib/api-client'
import { loadAppSettings } from '@/lib/config-storage'
import { hydrateWorkspaceImage } from '@/lib/workspace-storage'
import type { AgentImageAnalysis } from '@/types/agent'
import type { ModelSelection } from '@/types/app-settings'
import type { Workspace } from '@/types/workspace'

export type AgentRunProgress = AgentRunStep

export interface AgentRunResult {
  analysis: AgentImageAnalysis
  analysisRaw: string
  images: string[]
  text: string | null
  plan?: ApiAgentPlan
  toolTrace?: ApiToolRunTrace
}

export async function runWorkspaceAgent(
  workspace: Workspace,
  prompt: string,
  options?: {
    onProgress?: (step: AgentRunStep) => void
    modelSelection?: ModelSelection
    plan?: ApiAgentPlan
    onRun?: (controls: ApiAgentRunControls) => void
    origin?: ApiAgentRunOrigin
  },
): Promise<AgentRunResult> {
  const settings = loadAppSettings()
  const config = validateRunConfig(settings, options?.modelSelection)

  const hydrated = await hydrateWorkspaceImage(workspace)

  if (!hydrated.sourceImage) {
    throw new Error(translate('errors.uploadImageFirst'))
  }

  const runOptions: Parameters<typeof runAgentViaBackend>[3] = {
    onProgress: options?.onProgress,
  }
  if (options?.onRun) runOptions.onRun = options.onRun
  if (options?.origin) runOptions.origin = options.origin
  const result = options?.plan || workspace.currentVersionId
    ? await runAgentViaBackend(
      config,
      hydrated.sourceImage,
      prompt,
      runOptions,
      options?.plan,
      { workspaceId: workspace.id, versionId: workspace.currentVersionId },
    )
    : await runAgentViaBackend(config, hydrated.sourceImage, prompt, runOptions)

  return {
    analysis: result.analysis as AgentImageAnalysis,
    analysisRaw: result.analysisRaw,
    images: result.images,
    text: result.text,
    plan: result.plan,
    toolTrace: result.toolTrace,
  }
}

export async function previewWorkspaceAgentPlan(
  workspace: Workspace,
  prompt: string,
  options?: { modelSelection?: ModelSelection },
): Promise<AgentRunResult> {
  const settings = loadAppSettings()
  const config = validateRunConfig(settings, options?.modelSelection)
  const hydrated = await hydrateWorkspaceImage(workspace)
  if (!hydrated.sourceImage) throw new Error(translate('errors.uploadImageFirst'))
  const result = await previewAgentPlan(config, hydrated.sourceImage, prompt, {
    workspaceId: workspace.id,
    versionId: workspace.currentVersionId,
  })
  return {
    analysis: result.analysis as AgentImageAnalysis,
    analysisRaw: result.analysisRaw,
    images: [],
    text: null,
    plan: result.plan,
    toolTrace: result.toolTrace,
  }
}

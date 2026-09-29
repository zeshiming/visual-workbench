/**
 * Thin wrapper that bridges the workspace layer to the backend API.
 * No business logic — the Python backend handles everything.
 */
import { translate } from '@/i18n'

import { validateRunConfig } from '@/lib/app-settings'
import { runAgentViaBackend, type AgentRunStep } from '@/lib/api-client'
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
}

export async function runWorkspaceAgent(
  workspace: Workspace,
  prompt: string,
  options?: {
    onProgress?: (step: AgentRunStep) => void
    modelSelection?: ModelSelection
  },
): Promise<AgentRunResult> {
  const settings = loadAppSettings()
  const config = validateRunConfig(settings, options?.modelSelection)

  const hydrated = await hydrateWorkspaceImage(workspace)

  if (!hydrated.sourceImage) {
    throw new Error(translate('errors.uploadImageFirst'))
  }

  const result = await runAgentViaBackend(config, hydrated.sourceImage, prompt, {
    onProgress: options?.onProgress,
  })

  return {
    analysis: result.analysis as AgentImageAnalysis,
    analysisRaw: result.analysisRaw,
    images: result.images,
    text: result.text,
  }
}

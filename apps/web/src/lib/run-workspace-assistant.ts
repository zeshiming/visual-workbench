import { translate } from '@/i18n'

import { runAssistantViaBackend, type ApiAssistantMessage, type ApiAssistantResponse } from '@/lib/api-client'
import { validateRunConfig } from '@/lib/app-settings'
import { loadAppSettings } from '@/lib/config-storage'
import { hydrateWorkspaceImage } from '@/lib/workspace-storage'
import type { ModelSelection } from '@/types/app-settings'
import type { Workspace } from '@/types/workspace'

export async function runWorkspaceAssistant(
  workspace: Workspace,
  message: string,
  history: ApiAssistantMessage[],
  options?: { modelSelection?: ModelSelection; currentVersion?: string; sessionId?: string },
): Promise<ApiAssistantResponse> {
  const settings = loadAppSettings()
  const config = validateRunConfig(settings, options?.modelSelection)
  const hydrated = await hydrateWorkspaceImage(workspace)

  if (!hydrated.sourceImage) {
    throw new Error(translate('errors.uploadImageFirst'))
  }

  return runAssistantViaBackend(
    config,
    hydrated.sourceImage,
    message,
    history,
    options?.currentVersion,
    options?.sessionId,
    workspace.id,
  )
}

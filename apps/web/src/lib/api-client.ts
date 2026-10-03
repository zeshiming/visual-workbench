/**
 * API client for the Doushabao Python backend.
 *
 * All AI API calls are proxied through the backend. The frontend
 * is a pure UI layer — no business logic.
 */

/** Default backend URL — relative (Vite proxy / same-origin). Use `setApiBaseUrl()` for remote backends. */
let API_BASE = ''

export function getApiBaseUrl(): string {
  return API_BASE
}

export function setApiBaseUrl(url: string): void {
  API_BASE = url.replace(/\/+$/, '')
}

// ── Types (local, no @doushabao dependency) ───────────────────

export interface ApiModelEndpoint {
  host: string
  key: string
  model: string
}

export interface ApiCapabilityCheck {
  reachable: boolean
  model_available: boolean | null
  protocol: string
  capabilities: string[]
  message: string
}

export async function checkModelCapabilities(endpoint: ApiModelEndpoint, role: 'analysis' | 'edit'): Promise<ApiCapabilityCheck> {
  return apiJson<ApiCapabilityCheck>('POST', '/api/v1/ai/capabilities', { ...endpoint, role })
}

export interface ApiMcpServerConfig {
  id: string
  name: string
  transport: 'http' | 'stdio'
  url?: string | null
  enabled: boolean
  allowedTools: string[]
  secret_ref?: string | null
}

export interface ApiSkillManifest {
  id: string
  name: string
  version: string
  description: string
  tools: string[]
  enabled: boolean
}

export interface ApiAgentExtensions {
  mcpServers: ApiMcpServerConfig[]
  skills: ApiSkillManifest[]
}

export async function listAgentExtensions(): Promise<ApiAgentExtensions> {
  return apiJson<ApiAgentExtensions>('GET', '/api/v1/agent/extensions')
}

export async function addMcpExtension(input: { id: string; name: string; url: string }): Promise<void> {
  await apiJson('POST', '/api/v1/agent/extensions/mcp', {
    id: input.id, name: input.name, transport: 'http', url: input.url, enabled: false,
  })
}

export async function setMcpExtensionEnabled(id: string, enabled: boolean): Promise<void> {
  await apiJson('POST', `/api/v1/agent/extensions/mcp/${encodeURIComponent(id)}/${enabled ? 'enable' : 'disable'}`)
}

export async function removeMcpExtension(id: string): Promise<void> {
  await apiJson('DELETE', `/api/v1/agent/extensions/mcp/${encodeURIComponent(id)}`)
}

export async function discoverMcpExtension(id: string): Promise<string[]> {
  const result = await apiJson<{ tools: string[] }>('POST', `/api/v1/agent/extensions/mcp/${encodeURIComponent(id)}/discover`)
  return result.tools
}

export async function checkMcpExtension(id: string): Promise<{ reachable: boolean; protocolVersion?: string | null }> {
  return apiJson('POST', `/api/v1/agent/extensions/mcp/${encodeURIComponent(id)}/check`)
}

export async function allowMcpTool(id: string, toolName: string): Promise<void> {
  await apiJson('POST', `/api/v1/agent/extensions/mcp/${encodeURIComponent(id)}/allow-tool?tool_name=${encodeURIComponent(toolName)}`)
}

export async function denyMcpTool(id: string, toolName: string): Promise<void> {
  await apiJson('POST', `/api/v1/agent/extensions/mcp/${encodeURIComponent(id)}/deny-tool?tool_name=${encodeURIComponent(toolName)}`)
}

export async function addSkillExtension(input: { id: string; name: string; description?: string; instructions?: string }): Promise<void> {
  await apiJson('POST', '/api/v1/agent/extensions/skills', {
    id: input.id, name: input.name, version: '1', description: input.description ?? '', instructions: input.instructions ?? '', tools: [], enabled: false,
  })
}

export async function setSkillExtensionEnabled(id: string, enabled: boolean): Promise<void> {
  await apiJson('POST', `/api/v1/agent/extensions/skills/${encodeURIComponent(id)}/${enabled ? 'enable' : 'disable'}`)
}

export async function removeSkillExtension(id: string): Promise<void> {
  await apiJson('DELETE', `/api/v1/agent/extensions/skills/${encodeURIComponent(id)}`)
}

export interface ApiAssistantMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ApiAssistantResponse {
  session_id?: string | null
  message_id?: string | null
  reply: string
  intent: 'answer' | 'edit' | 'workflow'
  action: 'none' | 'preview_edit' | 'workflow'
  suggested_prompt: string
  trace: {
    model?: string
    protocol?: string
    status?: string
    durationMs?: number
    requestId?: string
  }
}

export async function createAssistantSession(workspaceId: string, currentVersion = 'current'): Promise<{ sessionId: string }> {
  return apiJson<{ sessionId: string }>('POST', '/api/v1/assistant/sessions', {
    workspace_id: workspaceId, current_version: currentVersion,
  })
}

export async function deleteAssistantSession(sessionId: string): Promise<void> {
  await apiJson<{ ok: boolean }>('DELETE', `/api/v1/assistant/sessions/${encodeURIComponent(sessionId)}`)
}

export interface ApiAssistantSessionMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  intent?: string
  action?: string
  suggested_prompt?: string
  version?: string
  created_at: number
}

export async function getAssistantSession(sessionId: string): Promise<{
  sessionId: string
  workspaceId: string
  currentVersion: string
  messages: ApiAssistantSessionMessage[]
}> {
  return apiJson('GET', `/api/v1/assistant/sessions/${encodeURIComponent(sessionId)}`)
}

export async function runAssistantViaBackend(
  config: { analysis: ApiModelEndpoint; edit: ApiModelEndpoint },
  imageDataUrl: string,
  message: string,
  history: ApiAssistantMessage[],
  currentVersion = 'current',
  sessionId?: string,
  workspaceId?: string,
): Promise<ApiAssistantResponse> {
  return apiJson<ApiAssistantResponse>('POST', '/api/v1/assistant/respond', {
    config,
    content: { content: message, image: imageDataUrl },
    history: history.slice(-10),
    current_version: currentVersion,
    session_id: sessionId,
    workspace_id: workspaceId,
  })
}

export interface ApiAgentRunResult {
  analysis: Record<string, unknown>
  analysisRaw: string
  images: string[]
  text: string | null
  plan?: ApiAgentPlan
  toolTrace?: ApiToolRunTrace
}

export type ApiAgentPlanPreviewResult = Pick<ApiAgentRunResult, 'analysis' | 'analysisRaw' | 'plan' | 'toolTrace'>

export async function previewAgentPlan(
  config: { analysis: ApiModelEndpoint; edit: ApiModelEndpoint },
  imageDataUrl: string,
  prompt: string,
  context?: { workspaceId?: string; versionId?: string | null },
): Promise<ApiAgentPlanPreviewResult> {
  return apiJson<ApiAgentPlanPreviewResult>('POST', '/api/v1/agent/plan', {
    config: {
      analysis: config.analysis,
      edit: config.edit,
    },
    content: { content: prompt, image: imageDataUrl },
    styles: [{ style: '' }],
    workspaceId: context?.workspaceId,
    versionId: context?.versionId ?? undefined,
  })
}

export interface ApiAgentPlanStep {
  id: string
  tool: string
  params: Record<string, unknown>
  depends_on: string[]
  rationale: string
}

export interface ApiAgentPlan {
  approval_id?: string
  version: '1'
  goal: string
  execution: 'local' | 'ai' | 'hybrid'
  steps: ApiAgentPlanStep[]
}

export interface ApiToolRunTrace {
  runs: Array<{
    stepId: string
    tool: string
    status: 'executed' | 'deferred' | 'failed' | 'skipped'
    message: string
  }>
  hasFailures: boolean
  aiCalls?: Array<{
    model: string
    protocol: string
    status: string
    durationMs: number
    requestId?: string
    error?: string
  }>
}

export interface ApiBatchToolEvent {
  type: 'start' | 'progress' | 'status' | 'done' | 'cancelled' | 'error'
  processed?: number
  total?: number
  sourceId?: string
  outputId?: string
  filename?: string
  message?: string
}

export interface ApiBatchJobControls {
  jobId: string
  pause: () => Promise<void>
  resume: () => Promise<void>
  cancel: () => Promise<void>
  retry: () => Promise<void>
}

export interface ApiAgentRunControls {
  runId: string
  pause: () => Promise<void>
  resume: () => Promise<void>
  cancel: () => Promise<void>
}

interface ApiDurableAgentResult {
  analysis: Record<string, unknown>
  analysisRaw: string
  images: string[]
  text: string | null
  plan?: ApiAgentPlan
  toolTrace?: ApiToolRunTrace
}

interface ApiAgentRunSnapshot {
  status: string
  result?: ApiDurableAgentResult | null
  error?: string
  events?: Array<{
    sequence: number
    type: string
    status?: string
    payload?: { phase?: string }
  }>
}

async function getAgentRunSnapshot(runId: string): Promise<ApiAgentRunSnapshot> {
  return apiJson<ApiAgentRunSnapshot>('GET', `/api/v1/agent/runs/${encodeURIComponent(runId)}`)
}

async function recoverCompletedAgentRun(
  runId: string,
  onProgress?: (step: AgentRunStep) => void,
  afterSequence = 0,
): Promise<ApiDurableAgentResult> {
  let lastSequence = afterSequence
  for (let attempt = 0; attempt < 12; attempt += 1) {
    const snapshot = await getAgentRunSnapshot(runId)
    for (const event of snapshot.events ?? []) {
      if (event.sequence <= lastSequence) continue
      lastSequence = event.sequence
      if (event.type === 'progress' && event.payload?.phase) {
        onProgress?.(event.payload.phase as AgentRunStep)
      }
    }
    if (snapshot.status === 'completed' && snapshot.result) return snapshot.result
    if (snapshot.status === 'failed' || snapshot.status === 'cancelled') {
      throw new Error(snapshot.error || 'Agent 任务失败')
    }
    if (snapshot.status === 'needs_review') {
      throw new Error(snapshot.error || 'Agent 任务需要人工核对，未自动重试模型请求')
    }
    await new Promise((resolve) => window.setTimeout(resolve, 250))
  }
  throw new Error('Agent 流连接中断，任务状态仍未确认，请稍后查看运行记录。')
}

export type ApiAgentRunOrigin = 'direct' | 'assistant_handoff'

export interface ApiEditorRunResult {
  run_id?: string | null
  images: string[]
  text: string | null
}

// ── Internal helpers ──────────────────────────────────────────

async function post<T>(path: string, body: unknown): Promise<T> {
  return apiJson<T>('POST', path, body)
}

async function apiJson<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(`后端请求失败 (${response.status}): ${text || response.statusText}`)
  }

  return response.json() as Promise<T>
}

// ── Agent Run ─────────────────────────────────────────────────

export type AgentRunStep = 'analysis' | 'edit'

export interface AgentRunOptions {
  onProgress?: (step: AgentRunStep) => void
  runId?: string
  onRun?: (controls: ApiAgentRunControls) => void
  origin?: ApiAgentRunOrigin
}

/**
 * Run the full Agent workflow via the Python backend.
 * Reads the streaming NDJSON response to fire onProgress at the right time.
 */
export async function runAgentViaBackend(
  config: { analysis: ApiModelEndpoint; edit: ApiModelEndpoint },
  imageDataUrl: string,
  prompt: string,
  options: AgentRunOptions = {},
  plan?: ApiAgentPlan,
  context?: { workspaceId?: string; versionId?: string | null },
): Promise<ApiAgentRunResult> {
  const runId = options.runId ?? crypto.randomUUID()
  const control = async (action: 'pause' | 'resume' | 'cancel'): Promise<void> => {
    const response = await fetch(`${API_BASE}/api/v1/agent/runs/${encodeURIComponent(runId)}/${action}`, { method: 'POST' })
    if (!response.ok) throw new Error(`Agent 任务操作失败 (${response.status}): ${await response.text()}`)
  }
  options.onRun?.({
    runId,
    pause: () => control('pause'),
    resume: () => control('resume'),
    cancel: () => control('cancel'),
  })
  const response = await fetch(`${API_BASE}/api/v1/agent/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      config: {
        analysis: { host: config.analysis.host, key: config.analysis.key, model: config.analysis.model },
        edit: { host: config.edit.host, key: config.edit.key, model: config.edit.model },
      },
      content: { content: prompt, image: imageDataUrl },
      styles: [{ style: '' }],
      plan,
      approved: Boolean(plan),
      origin: options.origin ?? 'direct',
      runId,
      workspaceId: context?.workspaceId,
      versionId: context?.versionId ?? undefined,
    }),
  })

  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(`后端请求失败 (${response.status}): ${text || response.statusText}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('后端未返回流式响应')
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let lastEventSequence = 0

  try {
    while (true) {
      const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

      for (const line of lines) {
      if (!line.trim()) continue

      let event: {
        type?: string
        phase?: string
        status?: string
        run_id?: string
        message?: string
        analysis?: Record<string, unknown>
        analysis_raw?: string
        images?: string[]
        text?: string | null
        plan?: ApiAgentPlan
        tool_trace?: ApiToolRunTrace
        sequence?: number
      }

      try {
        event = JSON.parse(line) as typeof event
      } catch {
        // Ignore a malformed/incomplete line and continue reading the stream.
        continue
      }

      if (event.type === 'progress') {
        if (typeof event.sequence === 'number') lastEventSequence = Math.max(lastEventSequence, event.sequence)
        options.onProgress?.(event.phase as AgentRunStep)
      } else if (event.type === 'cancelled') {
        throw new Error('Agent 任务已取消')
      } else if (event.type === 'needs_review') {
        throw new Error(event.message || 'Agent 任务需要人工核对，未自动重试模型请求')
      } else if (event.type === 'result') {
        return {
          analysis: event.analysis,
          analysisRaw: event.analysis_raw,
          images: event.images,
          text: event.text ?? null,
          plan: event.plan,
          toolTrace: event.tool_trace,
        } as ApiAgentRunResult
      } else if (event.type === 'error') {
        // Do not swallow the backend's provider/model error. The previous
        // parser caught this throw as if it were a JSON parse failure and
        // replaced the useful message with “后端未返回结果”.
        throw new Error(event.message || 'Agent 执行失败')
      }
      }
    }
  } catch (error) {
    // The provider run may still be progressing after the NDJSON connection
    // drops. Recover from the durable run record instead of issuing a second
    // model request.
    try {
      return await recoverCompletedAgentRun(runId, options.onProgress, lastEventSequence)
    } catch (recoveryError) {
      throw recoveryError instanceof Error ? recoveryError : error
    }
  }

  return await recoverCompletedAgentRun(runId, options.onProgress, lastEventSequence)
}

export async function runBatchToolViaBackend(
  workspaceId: string,
  input: {
    assetIds?: string[]
    feedbackId?: string
    referenceAssetId?: string
    operation: 'adjustments' | 'white_balance' | 'style' | 'reference_color'
    adjustments?: Record<string, number>
    styleId?: string
    referenceImage?: string
    priority?: 'high' | 'normal' | 'low'
  },
  onEvent?: (event: ApiBatchToolEvent) => void,
  onJob?: (controls: ApiBatchJobControls) => void,
): Promise<void> {
  const startResponse = await fetch(`${API_BASE}/api/v1/agent/batch/${encodeURIComponent(workspaceId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      assetIds: input.assetIds ?? [],
      feedbackId: input.feedbackId,
      referenceAssetId: input.referenceAssetId,
      operation: input.operation,
      adjustments: input.adjustments ?? {},
      styleId: input.styleId,
      referenceImage: input.referenceImage,
      priority: input.priority ?? 'normal',
    }),
  })
  if (!startResponse.ok) {
    throw new Error(`批量处理请求失败 (${startResponse.status}): ${await startResponse.text()}`)
  }
  const started = await startResponse.json() as { jobId?: string }
  if (!started.jobId) throw new Error('后端未返回批量任务 ID')

  const requestJobAction = async (jobId: string, action: 'pause' | 'resume' | 'cancel'): Promise<void> => {
    const response = await fetch(`${API_BASE}/api/v1/agent/batch/jobs/${encodeURIComponent(jobId)}/${action}`, {
      method: 'POST',
    })
    if (!response.ok) {
      throw new Error(`批量任务操作失败 (${response.status}): ${await response.text()}`)
    }
  }

  async function streamJob(jobId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/api/v1/agent/batch/jobs/${encodeURIComponent(jobId)}/events`)
    if (!response.ok) {
      throw new Error(`批量任务事件流请求失败 (${response.status}): ${await response.text()}`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('后端未返回批量处理流')
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.trim()) continue
        const event = JSON.parse(line) as ApiBatchToolEvent
        onEvent?.(event)
        if (event.type === 'error' && !event.sourceId) {
          throw new Error(event.message || '批量处理失败')
        }
        if (event.type === 'cancelled') return
      }
    }
  }

  const makeControls = (jobId: string): ApiBatchJobControls => ({
    jobId,
    pause: () => requestJobAction(jobId, 'pause'),
    resume: () => requestJobAction(jobId, 'resume'),
    cancel: () => requestJobAction(jobId, 'cancel'),
    retry: async () => {
      const response = await fetch(`${API_BASE}/api/v1/agent/batch/jobs/${encodeURIComponent(jobId)}/retry`, {
        method: 'POST',
      })
      if (!response.ok) {
        throw new Error(`重试批量任务失败 (${response.status}): ${await response.text()}`)
      }
      const retry = await response.json() as { jobId?: string }
      if (!retry.jobId) throw new Error('后端未返回重试任务 ID')
      onJob?.(makeControls(retry.jobId))
      await streamJob(retry.jobId)
    },
  })

  onJob?.(makeControls(started.jobId))
  await streamJob(started.jobId)
}

// ── Editor / Generate Image ───────────────────────────────────

export interface EditorMarkData {
  center_x: number
  center_y: number
  radius: number
  description: string
}

/**
 * Run the Editor workflow via the Python backend.
 * The backend builds the full prompt from marks.
 */
export async function generateImageViaBackend(
  config: { edit: ApiModelEndpoint },
  imageDataUrl: string,
  marks: EditorMarkData[],
  options: {
    imageConfig?: Record<string, unknown> | null
    runId?: string
    workspaceId?: string
    versionId?: string | null
    assetId?: string | null
  } = {},
): Promise<ApiEditorRunResult> {
  return post<ApiEditorRunResult>('/api/v1/editor/run', {
    config: {
      edit: { host: config.edit.host, key: config.edit.key, model: config.edit.model },
    },
    image: imageDataUrl,
    marks: marks.map((m) => ({
      center_x: m.center_x,
      center_y: m.center_y,
      radius: m.radius,
      description: m.description,
    })),
    styles: [{ style: '' }],
    image_config: options.imageConfig ?? null,
    run_id: options.runId,
    workspace_id: options.workspaceId,
    version_id: options.versionId ?? undefined,
    asset_id: options.assetId ?? undefined,
  })
}

// ═══════════════════════════════════════════════════════════════
// Settings (Theme + Locale + AppSettings + LastWorkspace)
// ═══════════════════════════════════════════════════════════════

export interface BackendSettings {
  app_settings: string
  theme: string
  locale: string
  last_workspace: string
}

export async function loadBackendSettings(): Promise<BackendSettings> {
  return apiJson<BackendSettings>('GET', '/api/v1/settings')
}

export async function saveBackendSettings(
  data: Partial<BackendSettings>,
): Promise<BackendSettings> {
  return apiJson<BackendSettings>('PUT', '/api/v1/settings', data)
}

export async function clearBackendSettings(): Promise<BackendSettings> {
  return apiJson<BackendSettings>('DELETE', '/api/v1/settings')
}

// ═══════════════════════════════════════════════════════════════
// Workspaces
// ═══════════════════════════════════════════════════════════════

export interface ApiWorkspace {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  hasSourceImage: boolean
  currentVersionId?: string | null
}

export interface ApiWorkspaceList {
  workspaces: ApiWorkspace[]
}

export interface ApiWorkspaceVersion {
  id: string
  parentId: string | null
  operation: string
  createdAt: number
  artifactId: string | null
  isCurrent: boolean
  assetId?: string | null
}

export function listWorkspaceVersions(workspaceId: string): Promise<ApiWorkspaceVersion[]> {
  return apiJson<ApiWorkspaceVersion[]>('GET', `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/versions`)
}

export async function getWorkspaceVersionImage(workspaceId: string, versionId: string): Promise<string | null> {
  const result = await apiJson<{ image: string | null }>(
    'GET', `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/versions/${encodeURIComponent(versionId)}/image`,
  )
  return result.image
}

export async function listBackendWorkspaces(): Promise<ApiWorkspace[]> {
  const res = await apiJson<ApiWorkspaceList>('GET', '/api/v1/workspaces')
  return res.workspaces
}

export async function getBackendWorkspace(id: string): Promise<ApiWorkspace> {
  return apiJson<ApiWorkspace>('GET', `/api/v1/workspaces/${encodeURIComponent(id)}`)
}

export async function createBackendWorkspace(
  data: ApiWorkspace,
): Promise<ApiWorkspace> {
  return apiJson<ApiWorkspace>('POST', '/api/v1/workspaces', data)
}

export async function updateBackendWorkspace(
  id: string,
  data: Partial<Pick<ApiWorkspace, 'title' | 'updatedAt' | 'hasSourceImage'>>,
): Promise<ApiWorkspace> {
  return apiJson<ApiWorkspace>('PUT', `/api/v1/workspaces/${encodeURIComponent(id)}`, data)
}

export async function commitBackendWorkspace(
  id: string,
    data: { title: string; createdAt: number; updatedAt: number; image?: string | null; expectedVersionId?: string | null; parentVersionId?: string | null; editorRunId?: string | null },
): Promise<ApiWorkspace> {
  return apiJson<ApiWorkspace>('PUT', `/api/v1/workspaces/${encodeURIComponent(id)}/commit`, data)
}

export async function deleteBackendWorkspace(id: string): Promise<void> {
  await apiJson<{ ok: boolean }>('DELETE', `/api/v1/workspaces/${encodeURIComponent(id)}`)
}

// Workspace images

export async function getBackendWorkspaceImage(
  id: string,
): Promise<string | null> {
  const res = await apiJson<{ image: string | null }>(
    'GET',
    `/api/v1/workspaces/${encodeURIComponent(id)}/image`,
  )
  return res.image
}

export async function saveBackendWorkspaceImage(
  id: string,
  image: string,
): Promise<void> {
  await apiJson<{ ok: boolean }>(
    'PUT',
    `/api/v1/workspaces/${encodeURIComponent(id)}/image`,
    { image },
  )
}

export async function deleteBackendWorkspaceImage(id: string): Promise<void> {
  await apiJson<{ ok: boolean }>(
    'DELETE',
    `/api/v1/workspaces/${encodeURIComponent(id)}/image`,
  )
}

// Reusable images belonging to a workspace.
export interface ApiAsset {
  id: string
  filename: string
  mediaType: string
  kind: 'import' | 'edit' | 'generated'
  createdAt: number
  sizeBytes: number
  width?: number | null
  height?: number | null
  metadata?: Record<string, string | number>
  pairGroup?: string | null
  pairRole?: 'raw' | 'jpeg' | 'other' | null
  feedbackId?: string | null
}

export interface ApiAssetContextItem extends ApiAsset {
  imageUrl: string
}

export interface ApiAssetContext {
  selectionSource: 'selected_assets' | 'feedback_id'
  assets: ApiAssetContextItem[]
  reference: ApiAssetContextItem | null
  missingIds: string[]
}

export interface ApiFeedbackRecord {
  id: string
  workspaceId: string
  feedbackId: string
  customerId: string
  message: string
  status: 'open' | 'processing' | 'resolved' | 'archived'
  createdAt: number
  updatedAt: number
}

function assetPath(workspaceId: string): string {
  return `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/assets`
}

export function listWorkspaceFeedback(workspaceId: string, query?: string): Promise<ApiFeedbackRecord[]> {
  const suffix = query?.trim() ? `?query=${encodeURIComponent(query.trim())}` : ''
  return apiJson<ApiFeedbackRecord[]>('GET', `${assetPath(workspaceId)}/feedback${suffix}`)
}

export async function updateWorkspaceFeedback(
  workspaceId: string,
  feedbackRecordId: string,
  input: { customerId?: string; message?: string; status?: ApiFeedbackRecord['status'] },
): Promise<ApiFeedbackRecord> {
  return apiJson<ApiFeedbackRecord>(
    'PUT',
    `${assetPath(workspaceId)}/feedback/${encodeURIComponent(feedbackRecordId)}`,
    input,
  )
}

export function assetImageUrl(workspaceId: string, assetId: string): string {
  return `${API_BASE}${assetPath(workspaceId)}/${encodeURIComponent(assetId)}/image`
}

export function listWorkspaceAssets(workspaceId: string): Promise<ApiAsset[]> {
  return apiJson<ApiAsset[]>('GET', assetPath(workspaceId))
}

export function resolveWorkspaceAssetContext(
  workspaceId: string,
  input: { assetIds?: string[]; feedbackId?: string; referenceAssetId?: string },
): Promise<ApiAssetContext> {
  return apiJson<ApiAssetContext>('POST', `${assetPath(workspaceId)}/context`, {
    assetIds: input.assetIds ?? [],
    feedbackId: input.feedbackId,
    referenceAssetId: input.referenceAssetId,
  })
}

export async function uploadWorkspaceAsset(
  workspaceId: string,
  file: File,
  kind: ApiAsset['kind'] = 'import',
  feedbackId?: string,
): Promise<ApiAsset> {
  const body = new FormData()
  body.append('file', file)
  body.append('kind', kind)
  if (feedbackId?.trim()) body.append('feedback_id', feedbackId.trim())
  const response = await fetch(`${API_BASE}${assetPath(workspaceId)}`, { method: 'POST', body })
  if (!response.ok) {
    throw new Error(`图片导入失败 (${response.status}): ${await response.text()}`)
  }
  return response.json() as Promise<ApiAsset>
}

export async function deleteWorkspaceAsset(workspaceId: string, assetId: string): Promise<void> {
  await apiJson<{ ok: boolean }>('DELETE', `${assetPath(workspaceId)}/${encodeURIComponent(assetId)}`)
}

export async function exportWorkspaceAssets(
  workspaceId: string,
  assetIds: string[],
): Promise<Blob> {
  const response = await fetch(`${API_BASE}${assetPath(workspaceId)}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ assetIds }),
  })
  if (!response.ok) {
    throw new Error(`导出失败 (${response.status}): ${await response.text()}`)
  }
  return response.blob()
}

// ═══════════════════════════════════════════════════════════════
// Health Check
// ═══════════════════════════════════════════════════════════════

export interface HealthStatus {
  status: string
  version: string
}

export async function checkBackendHealth(): Promise<HealthStatus> {
  return apiJson<HealthStatus>('GET', '/health')
}

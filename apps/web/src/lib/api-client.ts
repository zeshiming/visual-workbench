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

export interface ApiAgentRunResult {
  analysis: Record<string, unknown>
  analysisRaw: string
  images: string[]
  text: string | null
}

export interface ApiEditorRunResult {
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
): Promise<ApiAgentRunResult> {
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

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (!line.trim()) continue

      try {
        const event = JSON.parse(line)

        if (event.type === 'progress') {
          options.onProgress?.(event.phase as AgentRunStep)
        } else if (event.type === 'result') {
          return {
            analysis: event.analysis,
            analysisRaw: event.analysis_raw,
            images: event.images,
            text: event.text ?? null,
          } as ApiAgentRunResult
        } else if (event.type === 'error') {
          throw new Error(event.message || 'Agent 执行失败')
        }
      } catch (parseErr) {
        if (parseErr instanceof Error && parseErr.message !== 'Agent 执行失败') {
          continue
        }
        throw parseErr
      }
    }
  }

  throw new Error('后端未返回结果')
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
}

export interface ApiWorkspaceList {
  workspaces: ApiWorkspace[]
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

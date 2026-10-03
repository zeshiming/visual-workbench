import { beforeEach, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

beforeEach(() => fetchMock.mockReset())

it('recovers a completed Agent result after the stream ends without a result event', async () => {
  const stream = {
    getReader: () => ({
      read: vi.fn()
        .mockResolvedValueOnce({ done: true, value: undefined }),
    }),
  }
  fetchMock.mockResolvedValueOnce({ ok: true, body: stream })
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      status: 'completed',
      result: { analysis: {}, analysisRaw: '{}', images: ['result'], text: null },
    }) })

  const { runAgentViaBackend } = await import('../lib/api-client')
  const result = await runAgentViaBackend(
    { analysis: { host: 'https://example.com/v1', key: 'a', model: 'a' }, edit: { host: 'https://example.com/v1', key: 'e', model: 'e' } },
    'data:image/png;base64,image', 'edit', {}, undefined,
  )
  expect(result.images).toEqual(['result'])
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it('replays durable progress events after a stream disconnect without rerunning the model', async () => {
  const stream = {
    getReader: () => ({
      read: vi.fn().mockResolvedValueOnce({ done: true, value: undefined }),
    }),
  }
  fetchMock.mockResolvedValueOnce({ ok: true, body: stream })
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      status: 'completed',
      events: [{ sequence: 2, type: 'progress', payload: { phase: 'edit' } }],
      result: { analysis: {}, analysisRaw: '{}', images: ['recovered'], text: null },
    }) })

  const progress = vi.fn()
  const { runAgentViaBackend } = await import('../lib/api-client')
  const result = await runAgentViaBackend(
    { analysis: { host: 'https://example.com/v1', key: 'a', model: 'a' }, edit: { host: 'https://example.com/v1', key: 'e', model: 'e' } },
    'data:image/png;base64,image', 'edit', { onProgress: progress }, undefined,
  )
  expect(result.images).toEqual(['recovered'])
  expect(progress).toHaveBeenCalledWith('edit')
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it('surfaces needs_review instead of polling an unknown model result forever', async () => {
  const stream = {
    getReader: () => ({
      read: vi.fn().mockResolvedValueOnce({ done: true, value: undefined }),
    }),
  }
  fetchMock.mockResolvedValueOnce({ ok: true, body: stream })
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      status: 'needs_review',
      error: '图片模型请求结果未知，请人工核对。',
    }) })

  const { runAgentViaBackend } = await import('../lib/api-client')
  await expect(runAgentViaBackend(
    { analysis: { host: 'https://example.com/v1', key: 'a', model: 'a' }, edit: { host: 'https://example.com/v1', key: 'e', model: 'e' } },
    'data:image/png;base64,image', 'edit', {}, undefined,
  )).rejects.toThrow('图片模型请求结果未知')
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

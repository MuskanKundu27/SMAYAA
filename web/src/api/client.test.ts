import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ApiError,
  apiFetch,
  hasAccessToken,
  login,
  refreshAccessToken,
  resetClientForTests,
  setSessionEndedHandler,
} from './client'

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const token = (value: string) => json(200, { access_token: value, token_type: 'bearer', expires_in: 900 })
const unauthorized = () => json(401, { error: { code: 'unauthorized', message: 'Please log in.', details: [] } })

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  resetClientForTests()
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function authHeaderOfCall(index: number): string | null {
  const init = fetchMock.mock.calls[index][1] as RequestInit
  return new Headers(init.headers).get('Authorization')
}

describe('login', () => {
  it('stores the access token and sends it on later requests', async () => {
    fetchMock.mockResolvedValueOnce(token('abc')).mockResolvedValueOnce(json(200, { ok: true }))

    await login('operator1', 'secret')
    await apiFetch('/me')

    expect(hasAccessToken()).toBe(true)
    expect(authHeaderOfCall(1)).toBe('Bearer abc')
  })

  it('turns an API error into an ApiError with the server message', async () => {
    fetchMock.mockResolvedValueOnce(unauthorized())

    await expect(login('x', 'y')).rejects.toEqual(new ApiError(401, 'unauthorized', 'Please log in.'))
  })
})

describe('apiFetch', () => {
  it('refreshes an expired token once and retries the request', async () => {
    fetchMock
      .mockResolvedValueOnce(token('old'))
      .mockResolvedValueOnce(unauthorized()) // /me with the expired token
      .mockResolvedValueOnce(token('new')) // /auth/refresh
      .mockResolvedValueOnce(json(200, { username: 'operator1' })) // retried /me

    await login('operator1', 'secret')
    const me = await apiFetch<{ username: string }>('/me')

    expect(me.username).toBe('operator1')
    expect(fetchMock.mock.calls[2][0]).toBe('/api/v1/auth/refresh')
    expect(authHeaderOfCall(3)).toBe('Bearer new')
  })

  it('ends the session when the refresh also fails', async () => {
    const ended = vi.fn()
    setSessionEndedHandler(ended)
    fetchMock
      .mockResolvedValueOnce(unauthorized()) // request
      .mockResolvedValueOnce(unauthorized()) // refresh

    await expect(apiFetch('/me')).rejects.toBeInstanceOf(ApiError)
    expect(ended).toHaveBeenCalledOnce()
    expect(hasAccessToken()).toBe(false)
  })

  it('shares one refresh call between concurrent requests', async () => {
    fetchMock.mockResolvedValue(token('fresh'))

    await Promise.all([refreshAccessToken(), refreshAccessToken(), refreshAccessToken()])

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('does not end the session on a 403', async () => {
    const ended = vi.fn()
    setSessionEndedHandler(ended)
    fetchMock.mockResolvedValueOnce(json(403, { error: { code: 'forbidden', message: 'No.', details: [] } }))

    await expect(apiFetch('/users')).rejects.toMatchObject({ status: 403, code: 'forbidden' })
    expect(ended).not.toHaveBeenCalled()
  })
})

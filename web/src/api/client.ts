// Talks to the SMAYAA API.
//
// - The access token lives only in memory (never localStorage), so injected scripts can't read
//   it from storage. It is lost on page reload; we then get a new one with the refresh cookie.
// - The refresh token is an httpOnly cookie the browser sends to /api/v1/auth/* automatically.
// - On a 401 we refresh once and retry. Concurrent requests share one refresh call.

const API = '/api/v1'

export interface ErrorDetail {
  field?: string
  message: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: ErrorDetail[]

  constructor(status: number, code: string, message: string, details: ErrorDetail[] = []) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

let accessToken: string | null = null
let refreshInFlight: Promise<boolean> | null = null
let onSessionEnded: () => void = () => {}

/** Called when the session can't be renewed (e.g. user deactivated); the app shows login. */
export function setSessionEndedHandler(handler: () => void): void {
  onSessionEnded = handler
}

export function hasAccessToken(): boolean {
  return accessToken !== null
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as {
      error?: { code: string; message: string; details?: ErrorDetail[] }
    }
    if (body.error) {
      return new ApiError(response.status, body.error.code, body.error.message, body.error.details)
    }
  } catch {
    // not JSON (e.g. proxy error page)
  }
  return new ApiError(response.status, 'http_error', `Request failed (${response.status})`)
}

async function storeTokenFrom(response: Response): Promise<void> {
  const body = (await response.json()) as { access_token: string }
  accessToken = body.access_token
}

/** Get a new access token using the refresh cookie. Returns false if the session is over. */
export function refreshAccessToken(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const response = await fetch(`${API}/auth/refresh`, { method: 'POST' })
      if (!response.ok) {
        accessToken = null
        return false
      }
      await storeTokenFrom(response)
      return true
    } catch {
      accessToken = null
      return false
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}

function withAuth(init: RequestInit): RequestInit {
  const headers = new Headers(init.headers)
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  return { ...init, headers }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response = await fetch(`${API}${path}`, withAuth(init))
  if (response.status === 401 && (await refreshAccessToken())) {
    response = await fetch(`${API}${path}`, withAuth(init))
  }
  if (response.status === 401) {
    accessToken = null
    onSessionEnded()
  }
  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function login(username: string, password: string): Promise<void> {
  const response = await fetch(`${API}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) throw await toApiError(response)
  await storeTokenFrom(response)
}

export async function logout(): Promise<void> {
  accessToken = null
  try {
    await fetch(`${API}/auth/logout`, { method: 'POST' })
  } catch {
    // Even if the server is unreachable, the local session is gone.
  }
}

/** Test helper: forget everything between tests. */
export function resetClientForTests(): void {
  accessToken = null
  refreshInFlight = null
  onSessionEnded = () => {}
}

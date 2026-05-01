const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'
const BASIC_AUTH_STORAGE_KEY = 'budget_basic_auth'

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: authHeaders(),
    credentials: 'include',
  })
  if (!response.ok) {
    throw await apiError(response)
  }
  return response.json() as Promise<T>
}

export async function apiPost<T>(path: string, body: unknown = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
    credentials: 'include',
  })
  if (!response.ok) {
    throw await apiError(response)
  }
  return response.json() as Promise<T>
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
    credentials: 'include',
  })
  if (!response.ok) {
    throw await apiError(response)
  }
  return response.json() as Promise<T>
}

export async function apiDelete(path: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'DELETE',
    headers: authHeaders(),
    credentials: 'include',
  })
  if (!response.ok) {
    throw await apiError(response)
  }
}

export async function apiGetText(path: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: authHeaders(),
    credentials: 'include',
  })
  if (!response.ok) {
    throw await apiError(response)
  }
  return response.text()
}

export function setBasicAuth(username: string, password: string) {
  window.localStorage.setItem(BASIC_AUTH_STORAGE_KEY, window.btoa(`${username}:${password}`))
}

function authHeaders(): Record<string, string> {
  const configuredToken = import.meta.env.VITE_API_BASIC_AUTH as string | undefined
  const token = configuredToken || window.localStorage.getItem(BASIC_AUTH_STORAGE_KEY)
  return token ? { Authorization: `Basic ${token}` } : {}
}

async function apiError(response: Response) {
  try {
    const payload = await response.json()
    return new Error(`${response.status}: ${JSON.stringify(payload)}`)
  } catch {
    return new Error(`API request failed: ${response.status}`)
  }
}

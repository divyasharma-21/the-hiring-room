const API = '/api'
const TOKEN_KEY = 'hr_token'

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {}
}

export async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  const res = await fetch(`${API}${path}`, { ...options, headers })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const msg = typeof data.detail === 'string' ? data.detail
      : Array.isArray(data.detail) ? data.detail.map((d) => d.msg || d).join(', ')
      : data.detail?.msg || 'Something went wrong. Please try again.'
    throw new Error(msg)
  }
  return data
}

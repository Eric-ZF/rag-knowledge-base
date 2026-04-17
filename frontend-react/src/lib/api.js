const API_BASE = 'http://124.156.204.163:8080'

let _token = localStorage.getItem('token') || ''

export function setToken(t) {
  _token = t
  if (t) localStorage.setItem('token', t)
  else localStorage.removeItem('token')
}

export function getToken() { return _token }

async function api(method, path, body, timeoutMs = 0) {
  const headers = { 'Content-Type': 'application/json' }
  if (_token) headers['Authorization'] = `Bearer ${_token}`
  const opts = { method, headers }
  if (body) opts.body = JSON.stringify(body)
  if (timeoutMs) opts.timeout = timeoutMs

  const r = await fetch(`${API_BASE}${path}`, opts)
  const data = await r.json()
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`)
  return data
}

export const login = (phone, password) =>
  api('POST', '/auth/login', { phone, password })

export const register = (phone, password) =>
  api('POST', '/auth/register', { phone, password })

export const setPassword = (phone, password) =>
  api('POST', '/auth/set-password', { phone, password })

export const getFolders = () => api('GET', '/papers/folders')

export const createFolder = (name, parentId) =>
  api('POST', '/papers/folders', { name, parent_id: parentId })

export const deleteFolder = (folderId) =>
  api('DELETE', `/papers/folders/${folderId}`)

export const getPapers = () => api('GET', '/papers')

export const deletePaper = (paperId) =>
  api('DELETE', `/papers/${paperId}`)

export const movePapers = (paperIds, folderId) =>
  api('POST', '/papers/move', { paper_ids: paperIds, folder_id: folderId })

export const uploadPaper = (formData) =>
  fetch(`${API_BASE}/papers/upload`, {
    method: 'POST',
    headers: _token ? { 'Authorization': `Bearer ${_token}` } : {},
    body: formData,
  }).then(r => r.json())

export const getQuota = () => api('GET', '/me/quota')

export const sendChat = (body, timeoutMs = 120000) =>
  api('POST', '/chat', body, timeoutMs)

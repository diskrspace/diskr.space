const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function request(path, options = {}) {
  const response = await fetch(`${base}/api${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload.detail || `请求失败 (${response.status})`)
  }
  return response.json()
}

export const api = {
  status: () => request('/status'),
  progress: () => request('/scan/progress'),
  startScan: () => request('/scan', { method: 'POST' }),
  stopScan: () => request('/scan/stop', { method: 'POST' }),
  search: (tags, page = 0) => request(`/files/search?${new URLSearchParams({ tags, page })}`),
  duplicates: (sinceSize = 0, onlyDirs = false, page = 0, pageSize = 50) =>
    request(`/duplicates?${new URLSearchParams({ since_size: sinceSize, only_dirs: onlyDirs, page, page_size: pageSize })}`),
  deleteDuplicate: id => request(`/duplicates/${id}`, { method: 'DELETE' }),
  settings: () => request('/settings'),
  saveSettings: value => request('/settings', { method: 'PUT', body: JSON.stringify(value) })
}

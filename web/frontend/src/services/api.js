const API_BASE = '/api'

// 请求缓存
const cache = new Map()
const CACHE_TTL = 5000 // 5秒缓存

// 待处理请求（用于去重）
const pendingRequests = new Map()

// 获取缓存
function getCache(key) {
  const item = cache.get(key)
  if (item && Date.now() - item.time < CACHE_TTL) {
    return item.data
  }
  cache.delete(key)
  return null
}

// 设置缓存
function setCache(key, data) {
  cache.set(key, { data, time: Date.now() })
}

// 清除缓存
export function clearCache(pattern) {
  if (pattern) {
    for (const key of cache.keys()) {
      if (key.includes(pattern)) {
        cache.delete(key)
      }
    }
  } else {
    cache.clear()
  }
}

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`
  const method = options.method || 'GET'
  const cacheKey = `${method}:${url}`

  // 只缓存 GET 请求
  if (method === 'GET') {
    // 检查缓存
    const cached = getCache(cacheKey)
    if (cached) {
      return cached
    }

    // 检查是否有相同的待处理请求
    if (pendingRequests.has(cacheKey)) {
      return pendingRequests.get(cacheKey)
    }
  }

  // 创建请求 Promise
  const requestPromise = (async () => {
    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        },
        ...options
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: '请求失败' }))
        throw new Error(error.detail || '请求失败')
      }

      const data = await response.json()

      // 缓存 GET 请求结果
      if (method === 'GET') {
        setCache(cacheKey, data)
      }

      return data
    } finally {
      // 清除待处理请求
      if (method === 'GET') {
        pendingRequests.delete(cacheKey)
      }
    }
  })()

  // 记录待处理请求
  if (method === 'GET') {
    pendingRequests.set(cacheKey, requestPromise)
  }

  return requestPromise
}

// 获取会话列表
export async function getSessions(skipCheck = false) {
  return request(`/sessions?skip_check=${skipCheck}`)
}

// 获取单个会话
export async function getSession(id, checkRefusal = true) {
  return request(`/sessions/${id}?check_refusal=${checkRefusal}`)
}

// 预览会话修改
export async function previewSession(id) {
  // 预览不使用缓存
  clearCache('preview')
  return request(`/sessions/${id}/preview`, { method: 'POST' })
}

// AI 改写
export async function aiRewriteSession(id) {
  clearCache('ai-rewrite')
  return request(`/sessions/${id}/ai-rewrite`, { method: 'POST' })
}

// 执行清理
export async function patchSession(id, replacements = null) {
  clearCache('sessions')
  const options = { method: 'POST' }
  if (replacements && replacements.length > 0) {
    options.body = JSON.stringify({ replacements })
  }
  return request(`/sessions/${id}/patch`, options)
}

// 列出备份
export async function listBackups(id) {
  return request(`/sessions/${id}/backups`)
}

// 还原备份
export async function restoreSession(id, backupFilename) {
  return request(`/sessions/${id}/restore?backup_filename=${encodeURIComponent(backupFilename)}`, { method: 'POST' })
}

// 获取设置
export async function getSettings() {
  return request('/settings')
}

// 更新设置
export async function updateSettings(settings) {
  return request('/settings', {
    method: 'PUT',
    body: JSON.stringify(settings)
  })
}

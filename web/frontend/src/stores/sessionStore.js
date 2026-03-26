import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '../services/api'

export const useSessionStore = defineStore('session', () => {
  const sessions = ref([])
  const selectedId = ref(null)
  const preview = ref(null)
  const loading = ref(false)
  const previewLoading = ref(false)
  const aiRewrite = ref(null)
  const aiRewriteLoading = ref(false)

  async function fetchSessions(checkRefusal = true) {
    loading.value = true
    try {
      // 加载会话列表，可选检测拒绝内容
      const data = await api.getSessions(!checkRefusal)
      sessions.value = data.sessions

      // 自动选中最新会话
      if (sessions.value.length > 0 && !selectedId.value) {
        await selectSession(sessions.value[0].id)
      }
    } catch (error) {
      console.error('Failed to fetch sessions:', error)
    } finally {
      loading.value = false
    }
  }

  async function selectSession(id) {
    selectedId.value = id
    preview.value = null
    aiRewrite.value = null

    // 获取会话详情（包含拒绝检测）
    previewLoading.value = true
    try {
      // 先获取会话详情（检测拒绝）
      const sessionDetail = await api.getSession(id, true)
      // 更新会话列表中的拒绝状态
      const idx = sessions.value.findIndex(s => s.id === id)
      if (idx >= 0) {
        sessions.value[idx] = sessionDetail
      }

      // 然后预览
      const data = await api.previewSession(id)
      preview.value = data
    } catch (error) {
      console.error('Failed to preview session:', error)
    } finally {
      previewLoading.value = false
    }
  }

  async function previewSession(id) {
    previewLoading.value = true
    try {
      const data = await api.previewSession(id || selectedId.value)
      preview.value = data
      return data
    } catch (error) {
      console.error('Failed to preview session:', error)
      throw error
    } finally {
      previewLoading.value = false
    }
  }

  async function requestAIRewrite(id) {
    aiRewriteLoading.value = true
    aiRewrite.value = null
    try {
      const data = await api.aiRewriteSession(id || selectedId.value)
      if (data.success) {
        aiRewrite.value = data
        // 更新预览中所有匹配的 changes
        if (preview.value && preview.value.changes.length > 0 && data.items) {
          for (const item of data.items) {
            const change = preview.value.changes.find(c => c.line_num === item.line_num)
            if (change) {
              change.replacement = item.replacement
              change._ai_generated = true
            }
          }
        }
      }
      return data
    } catch (error) {
      console.error('AI rewrite failed:', error)
      throw error
    } finally {
      aiRewriteLoading.value = false
    }
  }

  async function patchSession(id) {
    // 构建按行号的替换列表
    let replacements = null
    if (aiRewrite.value?.items?.length > 0) {
      replacements = aiRewrite.value.items.map(item => ({
        line_num: item.line_num,
        replacement_text: item.replacement
      }))
    }
    try {
      const data = await api.patchSession(id || selectedId.value, replacements)
      if (data.success) {
        aiRewrite.value = null
        await fetchSessions()
        const currentSession = sessions.value.find(s => s.id === selectedId.value)
        if (currentSession) {
          await previewSession(selectedId.value)
        }
      }
      return data
    } catch (error) {
      console.error('Failed to patch session:', error)
      throw error
    }
  }

  async function listBackups(id) {
    return api.listBackups(id || selectedId.value)
  }

  async function restoreSession(id, backupFilename) {
    const data = await api.restoreSession(id || selectedId.value, backupFilename)
    if (data.success) {
      api.clearCache('sessions')
      await fetchSessions()
      if (selectedId.value) {
        await previewSession(selectedId.value)
      }
    }
    return data
  }

  function getSelectedSession() {
    return sessions.value.find(s => s.id === selectedId.value)
  }

  return {
    sessions,
    selectedId,
    preview,
    loading,
    previewLoading,
    aiRewrite,
    aiRewriteLoading,
    fetchSessions,
    selectSession,
    previewSession,
    requestAIRewrite,
    patchSession,
    listBackups,
    restoreSession,
    getSelectedSession
  }
})

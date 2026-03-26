<template>
  <div class="action-bar">
    <div class="left-actions">
      <n-button
        :type="hasRefusalOnly ? 'error' : 'warning'"
        :disabled="!canPatch"
        :loading="patching"
        @click="handlePatch"
      >
        <template #icon>
          <n-icon><TrashOutline /></n-icon>
        </template>
        {{ hasRefusalOnly ? '执行清理' : '清理推理内容' }}
      </n-button>

      <n-button
        :disabled="!canAIRewrite"
        :loading="sessionStore.aiRewriteLoading"
        @click="handleAIAnalyze"
      >
        <template #icon>
          <n-icon><SparklesOutline /></n-icon>
        </template>
        {{ sessionStore.aiRewrite ? 'AI 已生成' : 'AI 分析' }}
        <n-tag v-if="!settingsStore.aiEnabled" size="small" type="info" style="margin-left: 4px">未配置</n-tag>
        <n-tag v-else-if="sessionStore.aiRewrite" size="small" type="success" style="margin-left: 4px">✓</n-tag>
      </n-button>

      <n-button
        :disabled="!canRestore"
        :loading="restoring"
        @click="handleRestore"
      >
        <template #icon>
          <n-icon><ArrowUndoOutline /></n-icon>
        </template>
        还原
      </n-button>
    </div>

    <div class="right-info">
      <n-tag v-if="lastResult" :type="lastResult.type">
        {{ lastResult.message }}
      </n-tag>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { useMessage, useDialog, NSelect } from 'naive-ui'
import { TrashOutline, SparklesOutline, ArrowUndoOutline } from '@vicons/ionicons5'
import { useSessionStore } from '../stores/sessionStore'
import { useLogStore } from '../stores/logStore'
import { useSettingsStore } from '../stores/settingsStore'

const message = useMessage()
const dialog = useDialog()
const sessionStore = useSessionStore()
const logStore = useLogStore()
const settingsStore = useSettingsStore()

onMounted(() => {
  settingsStore.loadSettings()
})

const patching = ref(false)
const restoring = ref(false)
const lastResult = ref(null)

const canPatch = computed(() => {
  const preview = sessionStore.preview
  return sessionStore.selectedId && preview && (preview.has_changes || preview.reasoning_count > 0)
})

const hasRefusalOnly = computed(() => {
  return sessionStore.preview?.has_changes === true
})

async function handlePatch() {
  if (!canPatch.value) return

  const preview = sessionStore.preview
  const session = sessionStore.getSelectedSession()
  const changesCount = preview?.changes?.length || 0
  const reasoningCount = preview?.reasoning_count || 0

  // 根据是否有拒绝内容显示不同的确认对话框
  if (!preview?.has_changes && reasoningCount > 0) {
    // 无拒绝内容，只有推理内容
    dialog.info({
      title: '确认清理推理内容',
      content: `会话 "${session?.id || sessionStore.selectedId}" 未检测到拒绝回复。\n\n但包含 ${reasoningCount} 条加密推理内容，清理后将删除这些内容。\n\n备份将保存到原文件同目录，扩展名为 .bak\n\n是否继续？`,
      positiveText: '确认清理',
      negativeText: '取消',
      onPositiveClick: () => {
        executePatch()
      }
    })
  } else {
    // 有拒绝内容
    dialog.warning({
      title: '确认执行清理',
      content: `即将清理会话 "${session?.id || sessionStore.selectedId}" 中的拒绝内容。\n\n拒绝回复: ${changesCount} 处\n推理内容: ${reasoningCount} 条\n\n备份将保存到原文件同目录，扩展名为 .bak\n\n此操作不可撤销，是否继续？`,
      positiveText: '确认执行',
      negativeText: '取消',
      onPositiveClick: () => {
        executePatch()
      }
    })
  }
}

async function executePatch() {
  patching.value = true
  lastResult.value = null
  logStore.addLog('开始执行清理...', 'info')

  try {
    const result = await sessionStore.patchSession()

    if (result.success) {
      message.success(result.message)
      lastResult.value = { type: 'success', message: result.message }
      logStore.addLog(result.message, 'success')

      if (result.backup_path) {
        logStore.addLog(`备份已保存: ${result.backup_path}`, 'info')
      }
    } else {
      message.error(result.message)
      lastResult.value = { type: 'error', message: result.message }
      logStore.addLog(result.message, 'error')
    }
  } catch (error) {
    message.error(error.message)
    lastResult.value = { type: 'error', message: error.message }
    logStore.addLog(error.message, 'error')
  } finally {
    patching.value = false
  }
}

const canRestore = computed(() => {
  const s = sessionStore.getSelectedSession()
  return sessionStore.selectedId && s?.has_backup
})

const canAIRewrite = computed(() => {
  return sessionStore.selectedId
    && sessionStore.preview?.has_changes
    && settingsStore.aiEnabled
    && !sessionStore.aiRewriteLoading
})

async function handleRestore() {
  if (!sessionStore.selectedId) return

  restoring.value = true
  try {
    const backups = await sessionStore.listBackups()
    if (!backups || backups.length === 0) {
      message.warning('没有可用的备份')
      return
    }

    // 构建备份选项列表
    const backupOptions = backups.map((b, i) => ({
      label: `${b.timestamp}  (${formatBackupSize(b.size)})`,
      value: b.filename
    }))

    selectedBackup = backupOptions[0].value
    dialog.warning({
      title: '选择备份进行还原',
      content: () => {
        return h('div', {}, [
          h('p', { style: 'margin-bottom: 12px; color: #999;' }, `共找到 ${backups.length} 个备份，选择一个进行还原：`),
          h(NSelect, {
            options: backupOptions,
            defaultValue: backupOptions[0].value,
            onUpdateValue: (v) => { selectedBackup = v }
          })
        ])
      },
      positiveText: '确认还原',
      negativeText: '取消',
      onPositiveClick: async () => {
        const filename = selectedBackup || backupOptions[0].value
        logStore.addLog(`正在还原备份: ${filename}`, 'info')
        try {
          const result = await sessionStore.restoreSession(null, filename)
          if (result.success) {
            message.success(result.message)
            lastResult.value = { type: 'success', message: result.message }
            logStore.addLog(result.message, 'success')
          } else {
            message.error(result.message)
            logStore.addLog(result.message, 'error')
          }
        } catch (e) {
          message.error(e.message)
          logStore.addLog(e.message, 'error')
        }
      }
    })
  } catch (error) {
    message.error('获取备份列表失败: ' + error.message)
    logStore.addLog(error.message, 'error')
  } finally {
    restoring.value = false
  }
}

let selectedBackup = null

function formatBackupSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

async function handleAIAnalyze() {
  if (!canAIRewrite.value) return
  logStore.addLog('正在请求 AI 改写...', 'info')
  try {
    const result = await sessionStore.requestAIRewrite()
    if (result.success) {
      const itemCount = result.items?.length || 0
      message.success(`AI 已生成 ${itemCount} 条改写内容`)
      logStore.addLog(`AI 已改写 ${itemCount} 处拒绝内容`, 'success')
    } else {
      message.error(result.error || 'AI 改写失败')
      logStore.addLog(result.error || 'AI 改写失败', 'error')
    }
  } catch (error) {
    message.error(error.message)
    logStore.addLog(error.message, 'error')
  }
}
</script>

<style scoped>
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-top: 1px solid #3a3a3a;
}

.left-actions {
  display: flex;
  gap: 12px;
}

.right-info {
  display: flex;
  align-items: center;
}
</style>

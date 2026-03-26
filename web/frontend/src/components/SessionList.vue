<template>
  <div class="session-list">
    <div class="list-header">
      <span class="title">会话列表</span>
      <div class="header-actions">
        <n-button text size="small" @click="refresh" :loading="loading">
          <template #icon>
            <n-icon><RefreshOutline /></n-icon>
          </template>
        </n-button>
      </div>
    </div>

    <!-- 搜索框 -->
    <div class="search-box">
      <n-input
        v-model:value="searchQuery"
        placeholder="搜索会话 ID..."
        clearable
        size="small"
      >
        <template #prefix>
          <n-icon><SearchOutline /></n-icon>
        </template>
      </n-input>
    </div>

    <!-- 过滤标签 -->
    <div class="filter-tabs">
      <n-button
        size="tiny"
        :type="filterMode === 'all' ? 'primary' : 'default'"
        :secondary="filterMode === 'all'"
        @click="filterMode = 'all'"
      >
        全部 {{ sessionStore.sessions.length }}
      </n-button>
      <n-button
        size="tiny"
        :type="filterMode === 'refusal' ? 'error' : 'default'"
        :secondary="filterMode === 'refusal'"
        @click="filterMode = 'refusal'"
      >
        有拒绝 {{ refusalCount }}
      </n-button>
      <n-button
        size="tiny"
        :type="filterMode === 'clean' ? 'success' : 'default'"
        :secondary="filterMode === 'clean'"
        @click="filterMode = 'clean'"
      >
        无拒绝 {{ sessionStore.sessions.length - refusalCount }}
      </n-button>
      <n-button
        size="tiny"
        :type="filterMode === 'patched' ? 'info' : 'default'"
        :secondary="filterMode === 'patched'"
        @click="filterMode = 'patched'"
      >
        已清理 {{ patchedCount }}
      </n-button>
    </div>

    <div class="list-scrollbar">
      <div v-if="loading" class="loading-state">
        <n-spin size="medium" />
      </div>
      <div v-else class="list-content">
        <n-empty v-if="filteredSessions.length === 0" description="暂无会话" />

        <!-- 按日期分组显示 -->
        <div v-for="group in groupedSessions" :key="group.label" class="date-group">
          <div class="date-label" @click="toggleGroup(group.label)">
            <n-icon class="group-icon" :class="{ expanded: expandedGroups.has(group.label) }">
              <ChevronDownOutline />
            </n-icon>
            <span>{{ group.label }}</span>
            <span class="count">{{ group.sessions.length }}</span>
          </div>

          <div v-show="expandedGroups.has(group.label)" class="group-sessions">
            <div
              v-for="session in group.sessions"
              :key="session.id"
              class="session-item"
              :class="{ selected: session.id === sessionStore.selectedId, 'has-refusal': session.has_refusal }"
            >
              <div class="session-main" @click="selectSession(session.id)">
                <div class="session-info">
                  <span class="session-id">{{ session.id }}</span>
                  <span class="session-time">{{ formatTime(session.mtime) }}</span>
                </div>
                <div class="session-meta">
                  <n-tag
                    v-if="session.has_refusal"
                    type="error"
                    size="small"
                  >
                    🚫 {{ session.refusal_count }}
                  </n-tag>
                  <n-tag v-else type="success" size="small">
                    ✅
                  </n-tag>
                  <n-tag
                    v-if="session.has_backup"
                    type="info"
                    size="small"
                  >
                    已清理
                  </n-tag>
                  <n-icon
                    class="expand-icon"
                    :class="{ expanded: expandedIds.has(session.id) }"
                    @click.stop="toggleExpand(session.id)"
                  >
                    <ChevronDownOutline />
                  </n-icon>
                </div>
              </div>

              <div v-show="expandedIds.has(session.id)" class="session-detail">
                <div class="detail-item">
                  <span class="label">文件名:</span>
                  <span class="value" :title="session.filename">{{ truncate(session.filename, 30) }}</span>
                </div>
                <div class="detail-item">
                  <span class="label">大小:</span>
                  <span class="value">{{ formatSize(session.size) }}</span>
                </div>
                <div class="detail-item">
                  <span class="label">修改时间:</span>
                  <span class="value">{{ session.mtime }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { RefreshOutline, ChevronDownOutline, SearchOutline } from '@vicons/ionicons5'
import { useSessionStore } from '../stores/sessionStore'

const sessionStore = useSessionStore()
const expandedIds = reactive(new Set())
const expandedGroups = reactive(new Set(['今天', '昨天']))
const searchQuery = ref('')
const filterMode = ref('refusal')  // 'all' | 'refusal' | 'clean' | 'patched'
const loading = ref(false)

const refusalCount = computed(() => {
  return sessionStore.sessions.filter(s => s.has_refusal).length
})

const patchedCount = computed(() => {
  return sessionStore.sessions.filter(s => s.has_backup).length
})

// 过滤后的会话列表
const filteredSessions = computed(() => {
  let list = sessionStore.sessions
  // 按拒绝状态过滤
  if (filterMode.value === 'refusal') {
    list = list.filter(s => s.has_refusal)
  } else if (filterMode.value === 'clean') {
    list = list.filter(s => !s.has_refusal)
  } else if (filterMode.value === 'patched') {
    list = list.filter(s => s.has_backup)
  }
  // 搜索过滤
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    list = list.filter(s =>
      s.id.toLowerCase().includes(query) ||
      s.filename.toLowerCase().includes(query)
    )
  }
  return list
})

// 按日期分组
const groupedSessions = computed(() => {
  const groups = {}
  // 使用本地时间，与 mtime 保持一致
  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
  const yd = new Date(Date.now() - 86400000)
  const yesterday = `${yd.getFullYear()}-${pad(yd.getMonth() + 1)}-${pad(yd.getDate())}`
  const wa = new Date(Date.now() - 7 * 86400000)
  const weekAgo = `${wa.getFullYear()}-${pad(wa.getMonth() + 1)}-${pad(wa.getDate())}`

  // 先按是否有拒绝内容排序，再按日期分组
  const sortedSessions = [...filteredSessions.value].sort((a, b) => {
    // 有拒绝内容的排前面
    if (a.has_refusal !== b.has_refusal) {
      return a.has_refusal ? -1 : 1
    }
    // 同类型按修改时间排序
    return b.mtime.localeCompare(a.mtime)
  })

  for (const session of sortedSessions) {
    // 用 mtime（最后修改时间）分组，而非文件名中的创建日期
    const mtimeDate = session.mtime.split(' ')[0]  // "2026-03-27 03:21:00" → "2026-03-27"
    let label
    if (mtimeDate === today) {
      label = '今天'
    } else if (mtimeDate === yesterday) {
      label = '昨天'
    } else if (mtimeDate >= weekAgo) {
      label = '本周'
    } else {
      label = '更早'
    }

    if (!groups[label]) {
      groups[label] = []
    }
    groups[label].push(session)
  }

  const order = ['今天', '昨天', '本周', '更早']
  return order
    .filter(label => groups[label])
    .map(label => ({
      label,
      sessions: groups[label]
    }))
})

function selectSession(id) {
  sessionStore.selectSession(id)
}

function toggleExpand(id) {
  if (expandedIds.has(id)) {
    expandedIds.delete(id)
  } else {
    expandedIds.add(id)
  }
}

function toggleGroup(label) {
  if (expandedGroups.has(label)) {
    expandedGroups.delete(label)
  } else {
    expandedGroups.add(label)
  }
}

async function refresh() {
  loading.value = true
  try {
    await sessionStore.fetchSessions()
  } finally {
    loading.value = false
  }
}

function truncate(str, len) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function formatTime(mtime) {
  const parts = mtime.split(' ')
  return parts.length > 1 ? parts[1].slice(0, 5) : mtime
}
</script>

<style scoped>
.session-list {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.list-header {
  flex-shrink: 0;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-border, #3a3a3a);
}

.title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-1, #fff);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.search-box {
  flex-shrink: 0;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border, #3a3a3a);
}

.filter-tabs {
  flex-shrink: 0;
  display: flex;
  gap: 6px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border, #3a3a3a);
}

.list-scrollbar {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
}

.list-content {
  padding: 8px 0;
}

.date-group {
  margin-bottom: 8px;
}

.date-label {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-3, #888);
  cursor: pointer;
  user-select: none;
}

.date-label:hover {
  color: var(--color-text-2, #aaa);
}

.group-icon {
  transition: transform 0.2s;
  font-size: 12px;
}

.group-icon.expanded {
  transform: rotate(0deg);
}

.group-icon:not(.expanded) {
  transform: rotate(-90deg);
}

.date-label .count {
  margin-left: auto;
  background: var(--color-bg-3, #3a3a3a);
  padding: 0 6px;
  border-radius: 10px;
  font-size: 11px;
}

.group-sessions {
  overflow: hidden;
}

.session-item {
  padding: 8px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--color-border-light, #2a2a2a);
  transition: background 0.2s;
}

.session-item:hover {
  background: var(--color-bg-2, #2a2a2a);
}

.session-item.selected {
  background: #2d4a3a;
}

/* 有拒绝内容的会话 - 高亮显示 */
.session-item.has-refusal {
  background: rgba(208, 48, 80, 0.1);
  border-left: 3px solid #d03050;
}

.session-item.has-refusal:hover {
  background: rgba(208, 48, 80, 0.15);
}

.session-item.has-refusal.selected {
  background: rgba(208, 48, 80, 0.2);
}

.session-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.session-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.session-id {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-1, #fff);
  font-family: monospace;
}

.session-time {
  font-size: 11px;
  color: var(--color-text-4, #666);
}

.session-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.expand-icon {
  transition: transform 0.2s;
  color: var(--color-text-3, #888);
  cursor: pointer;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.session-detail {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--color-border, #3a3a3a);
}

.detail-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
}

.detail-item .label {
  color: var(--color-text-3, #888);
  min-width: 60px;
}

.detail-item .value {
  color: var(--color-text-2, #ccc);
  font-family: monospace;
}
</style>

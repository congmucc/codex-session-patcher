<template>
  <n-config-provider :theme="darkTheme" :locale="naiveLocale" :date-locale="naiveDateLocale">
    <n-message-provider>
      <n-dialog-provider>
        <n-layout class="app-layout">
        <!-- 顶部 Header -->
        <n-layout-header bordered class="app-header">
          <div class="header-left">
            <n-button
              quaternary
              class="menu-toggle hide-tablet"
              @click="sidebarCollapsed = !sidebarCollapsed"
            >
              <template #icon>
                <n-icon><MenuOutline /></n-icon>
              </template>
            </n-button>
            <n-icon size="24" color="var(--color-primary)">
              <CodeSlash />
            </n-icon>
            <span class="title">Codex Session Patcher</span>
          </div>
          <div class="header-right">
            <LocaleSwitch />
          </div>
        </n-layout-header>

        <!-- Tab 导航 -->
        <n-tabs v-model:value="activeTab" type="line" class="main-tabs" @update:value="handleTabChange">
          <n-tab name="sessions">
            <template #icon>
              <n-icon><ListOutline /></n-icon>
            </template>
            {{ $t('nav.sessions') }}
          </n-tab>
          <n-tab name="enhance">
            <template #icon>
              <n-icon><SparklesOutline /></n-icon>
            </template>
            {{ $t('nav.enhance') }}
          </n-tab>
          <n-tab name="settings">
            <template #icon>
              <n-icon><SettingsOutline /></n-icon>
            </template>
            {{ $t('nav.settings') }}
          </n-tab>
          <n-tab name="help">
            <template #icon>
              <n-icon><HelpCircleOutline /></n-icon>
            </template>
            {{ $t('nav.help') }}
          </n-tab>
        </n-tabs>

        <!-- 主内容区 -->
        <n-layout has-sider class="app-content" v-show="activeTab === 'sessions'">
          <!-- 左侧会话列表 -->
          <n-layout-sider
            bordered
            :width="280"
            :collapsed-width="0"
            :collapsed="sidebarCollapsed"
            :native-scrollbar="false"
            class="session-sider"
            collapse-mode="transform"
            @collapse="sidebarCollapsed = true"
            @expand="sidebarCollapsed = false"
          >
            <SessionList />
          </n-layout-sider>

          <!-- 移动端遮罩 -->
          <div
            v-if="!sidebarCollapsed && isMobile"
            class="sidebar-overlay"
            @click="sidebarCollapsed = true"
          />

          <!-- 右侧内容区 -->
          <n-layout-content class="main-content">
            <PreviewPanel />
            <ActionBar />
          </n-layout-content>
        </n-layout>

        <!-- 其他 Tab 内容 -->
        <n-layout-content v-show="activeTab !== 'sessions'" class="tab-content">
          <PromptEnhancePanel v-if="activeTab === 'enhance'" />
          <SettingsPanel v-if="activeTab === 'settings'" />
          <HelpPanel v-if="activeTab === 'help'" />
        </n-layout-content>

        <!-- 底部日志面板 -->
        <LogPanel />
      </n-layout>
    </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { darkTheme, zhCN, dateZhCN, enUS, dateEnUS, NDialogProvider } from 'naive-ui'
import { CodeSlash, SettingsOutline, MenuOutline, ListOutline, SparklesOutline, HelpCircleOutline } from '@vicons/ionicons5'
import SessionList from './components/SessionList.vue'
import PreviewPanel from './components/PreviewPanel.vue'
import ActionBar from './components/ActionBar.vue'
import LogPanel from './components/LogPanel.vue'
import PromptEnhancePanel from './components/PromptEnhancePanel.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import HelpPanel from './components/HelpPanel.vue'
import LocaleSwitch from './components/LocaleSwitch.vue'
import { useSessionStore } from './stores/sessionStore'
import { useSettingsStore } from './stores/settingsStore'
import { useLogStore } from './stores/logStore'
import { useLocaleStore } from './stores/localeStore'

const { t } = useI18n()
const activeTab = ref('sessions')
const sidebarCollapsed = ref(false)
const isMobile = ref(false)
const sessionStore = useSessionStore()
const settingsStore = useSettingsStore()
const logStore = useLogStore()
const localeStore = useLocaleStore()

// Naive UI locale
const naiveLocale = computed(() => {
  return localeStore.currentLocale === 'en-US' ? enUS : zhCN
})

const naiveDateLocale = computed(() => {
  return localeStore.currentLocale === 'en-US' ? dateEnUS : dateZhCN
})

// 初始化：加载会话列表
sessionStore.fetchSessions()

// Tab 切换时加载设置
function handleTabChange(tab) {
  if (tab === 'settings') {
    settingsStore.loadSettings()
  }
}

// 响应式检测
const checkMobile = () => {
  isMobile.value = window.innerWidth < 768
  if (isMobile.value) {
    sidebarCollapsed.value = true
  }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

// WebSocket 连接管理
let ws = null
let reconnectTimer = null
const wsConnected = ref(false)

const connectWebSocket = () => {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${wsProtocol}//${window.location.host}/api/ws`

  ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    wsConnected.value = true
    console.log('WebSocket connected')
  }

  ws.onclose = () => {
    wsConnected.value = false
    console.log('WebSocket disconnected, reconnecting...')
    // 3秒后重连
    reconnectTimer = setTimeout(connectWebSocket, 3000)
  }

  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'log') {
        const { level, message } = data.data
        logStore.addLog(message, level)
      }
    } catch (e) {
      console.error('WebSocket message parse error:', e)
    }
  }
}

connectWebSocket()

// 组件卸载时清理 WebSocket
onUnmounted(() => {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
  }
  if (ws) {
    ws.close()
  }
})
</script>

<style scoped>
.app-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  height: var(--header-height);
  padding: 0 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--color-bg-1);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.menu-toggle {
  display: none;
}

.title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-1);
}

.main-tabs {
  padding: 0 16px;
  background: var(--color-bg-1);
  border-bottom: 1px solid var(--color-border);
}

.main-tabs :deep(.n-tabs-nav) {
  padding: 0;
}

.app-content {
  flex: 1;
  min-height: 0;
}

.session-sider {
  background: var(--color-bg-1);
}

.sidebar-overlay {
  display: none;
}

.main-content {
  display: flex;
  flex-direction: column;
  padding: 16px;
  padding-bottom: 56px; /* 日志面板收起时的高度 + 安全边距 */
  background: var(--color-bg-2);
}

.tab-content {
  flex: 1;
  padding: 16px;
  padding-bottom: 56px;
  background: var(--color-bg-2);
  overflow: auto;
}

/* 响应式布局 */
@media (max-width: 1024px) {
  .menu-toggle {
    display: flex;
  }

  .session-sider {
    position: fixed;
    top: calc(var(--header-height) + 40px);
    left: 0;
    bottom: 0;
    z-index: 100;
    background: var(--color-bg-1);
  }

  .sidebar-overlay {
    display: block;
    position: fixed;
    top: calc(var(--header-height) + 40px);
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 99;
  }
}

@media (max-width: 768px) {
  .main-content, .tab-content {
    padding: 12px;
  }
}
</style>

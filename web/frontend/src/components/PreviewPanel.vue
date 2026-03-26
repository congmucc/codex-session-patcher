<template>
  <div class="preview-panel">
    <div v-if="!session" class="empty-state">
      <n-empty description="请选择一个会话" />
    </div>

    <div v-else-if="!preview" class="empty-state">
      <n-spin size="large" />
    </div>

    <div v-else class="preview-container">
      <!-- Tab 切换 -->
      <div class="preview-tabs">
        <div
          class="tab-item"
          :class="{ active: activeTab === 'changes' }"
          @click="activeTab = 'changes'"
        >
          <n-icon><SwapHorizontalOutline /></n-icon>
          <span>修改预览</span>
          <n-tag v-if="preview.has_changes" type="warning" size="small" style="margin-left: 4px">
            {{ preview.changes.length }}
          </n-tag>
        </div>
        <div
          class="tab-item"
          :class="{ active: activeTab === 'diff' }"
          @click="activeTab = 'diff'"
        >
          <n-icon><CodeOutline /></n-icon>
          <span>Diff 视图</span>
        </div>
      </div>

      <!-- 修改预览 Tab -->
      <div v-show="activeTab === 'changes'" class="preview-scrollbar">
        <!-- 无拒绝回复但有序推理内容 -->
        <div v-if="!preview.has_changes && preview.reasoning_count > 0" class="empty-content">
          <n-empty type="info">
            <template #icon>
              <n-icon size="48" color="#2080f0">
                <InformationCircleOutline />
              </n-icon>
            </template>
            <template #description>
              <div class="reasoning-info">
                <p>当前会话无拒绝回复</p>
                <p>执行清理时将删除 <strong>{{ preview.reasoning_count }}</strong> 条推理内容</p>
              </div>
            </template>
          </n-empty>
        </div>

        <!-- 无任何修改 -->
        <div v-else-if="!preview.has_changes" class="empty-content">
          <n-empty description="当前会话无需清理" type="success">
            <template #icon>
              <n-icon size="48" color="#18a058">
                <CheckmarkCircleOutline />
              </n-icon>
            </template>
          </n-empty>
        </div>

        <div v-else class="preview-content">
          <!-- 推理内容提示 -->
          <div v-if="preview.reasoning_count > 0" class="reasoning-banner">
            <n-icon><InformationCircleOutline /></n-icon>
            <span>执行清理时还将删除 {{ preview.reasoning_count }} 条推理内容</span>
          </div>

          <div class="changes-list">
            <div
              v-for="(change, index) in preview.changes"
              :key="index"
              class="change-item"
            >
              <div class="change-header">
                <n-tag
                  :type="change.type === 'replace' ? 'warning' : 'error'"
                  size="small"
                >
                  {{ change.type === 'replace' ? '替换' : '删除' }}
                </n-tag>
                <span class="line-num">第 {{ change.line_num }} 行</span>
              </div>

              <div v-if="change.type === 'replace'" class="change-content">
                <div class="content-block original">
                  <div class="content-label">原始内容</div>
                  <pre>{{ change.original }}</pre>
                </div>
                <div class="content-arrow">
                  <n-icon size="20" color="#18a058">
                    <ArrowDownOutline />
                  </n-icon>
                </div>
                <div class="content-block replacement">
                  <div class="content-label">
                    替换为
                    <n-tag v-if="change._ai_generated" size="small" type="success" style="margin-left: 6px">AI 生成</n-tag>
                  </div>
                  <pre>{{ change.replacement }}</pre>
                </div>
              </div>

              <div v-else class="change-content">
                <div class="content-block deleted">
                  <div class="content-label">删除内容</div>
                  <pre>{{ change.content }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Diff 视图 Tab -->
      <div v-show="activeTab === 'diff'" class="preview-scrollbar">
        <!-- 已清理会话：显示清理前后对比 -->
        <div v-if="preview.diff_items && preview.diff_items.length > 0" class="diff-content">
          <div class="diff-header-banner">
            <n-icon><InformationCircleOutline /></n-icon>
            <span>清理前后对比（与最近一次备份对比）</span>
          </div>
          <div
            v-for="(item, index) in preview.diff_items"
            :key="'backup-' + index"
            class="diff-block"
          >
            <div class="diff-line deleted">
              <span class="line-number">{{ item.line_num || '-' }}</span>
              <span class="diff-marker">-</span>
              <pre class="diff-text">{{ item.before }}</pre>
            </div>
            <div class="diff-line added">
              <span class="line-number">{{ item.line_num || '-' }}</span>
              <span class="diff-marker">+</span>
              <pre class="diff-text">{{ item.after }}</pre>
            </div>
          </div>
        </div>

        <!-- 未清理会话：显示待修改的 diff -->
        <div v-else-if="preview.has_changes" class="diff-content">
          <div
            v-for="(change, index) in preview.changes"
            :key="index"
            class="diff-block"
          >
            <!-- 删除行 -->
            <div v-if="change.type === 'delete'" class="diff-line deleted">
              <span class="line-number">{{ change.line_num }}</span>
              <span class="diff-marker">-</span>
              <pre class="diff-text">{{ change.content || '推理内容' }}</pre>
            </div>

            <!-- 替换：显示删除和新增 -->
            <template v-else-if="change.type === 'replace'">
              <div class="diff-line deleted">
                <span class="line-number">{{ change.line_num }}</span>
                <span class="diff-marker">-</span>
                <pre class="diff-text">{{ change.original }}</pre>
              </div>
              <div class="diff-line added">
                <span class="line-number">{{ change.line_num }}</span>
                <span class="diff-marker">+</span>
                <pre class="diff-text">{{ change.replacement }}</pre>
                <n-tag v-if="change._ai_generated" size="small" type="success" style="margin-left: 6px; flex-shrink: 0">AI</n-tag>
              </div>
            </template>
          </div>
        </div>

        <div v-else class="empty-content">
          <n-empty description="无修改内容" type="success">
            <template #icon>
              <n-icon size="48" color="#18a058">
                <CheckmarkCircleOutline />
              </n-icon>
            </template>
          </n-empty>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { CheckmarkCircleOutline, ArrowDownOutline, SwapHorizontalOutline, CodeOutline, InformationCircleOutline } from '@vicons/ionicons5'
import { useSessionStore } from '../stores/sessionStore'

const sessionStore = useSessionStore()
const activeTab = ref('changes')

const session = computed(() => sessionStore.getSelectedSession())
const preview = computed(() => sessionStore.preview)

// 已清理会话（有备份）默认显示 Diff 视图
watch(() => sessionStore.selectedId, () => {
  const s = sessionStore.getSelectedSession()
  if (s?.has_backup) {
    activeTab.value = 'diff'
  } else {
    activeTab.value = 'changes'
  }
})
</script>

<style scoped>
.preview-panel {
  flex: 1;
  overflow: hidden;
  background: var(--color-bg-1, #1a1a1a);
  border-radius: 8px;
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.empty-state {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.preview-tabs {
  display: flex;
  border-bottom: 1px solid var(--color-border, #3a3a3a);
  padding: 0 16px;
  flex-shrink: 0;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  font-size: 13px;
  color: var(--color-text-3, #888);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: all 0.2s;
}

.tab-item:hover {
  color: var(--color-text-2, #ccc);
}

.tab-item.active {
  color: var(--color-primary, #18a058);
  border-bottom-color: var(--color-primary, #18a058);
}

.preview-scrollbar {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.empty-content {
  padding: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-content {
  padding: 16px;
}

.changes-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.change-item {
  background: var(--color-bg-2, #2d2d2d);
  border-radius: 8px;
  padding: 12px;
}

.change-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.line-num {
  font-size: 12px;
  color: var(--color-text-3, #888);
  font-family: monospace;
}

.change-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.content-block {
  padding: 12px;
  border-radius: 6px;
}

.content-block.original {
  background: #3d2d2d;
  border-left: 3px solid #d03050;
}

.content-block.replacement {
  background: #2d3d2d;
  border-left: 3px solid #18a058;
}

.content-block.deleted {
  background: #3d2d2d;
  border-left: 3px solid #909090;
}

.content-label {
  font-size: 11px;
  color: var(--color-text-3, #888);
  margin-bottom: 8px;
  text-transform: uppercase;
}

.content-block pre {
  font-size: 13px;
  color: var(--color-text-2, #ccc);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  line-height: 1.5;
}

.content-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px 0;
}

/* Diff 视图样式 */
.diff-content {
  padding: 16px;
  font-family: 'Fira Code', 'SF Mono', Monaco, monospace;
}

.diff-block {
  margin-bottom: 8px;
}

.diff-line {
  display: flex;
  align-items: flex-start;
  padding: 4px 0;
  font-size: 13px;
  line-height: 1.5;
}

.diff-line.deleted {
  background: rgba(208, 48, 80, 0.15);
}

.diff-line.added {
  background: rgba(24, 160, 88, 0.15);
}

.line-number {
  min-width: 40px;
  padding: 0 8px;
  color: var(--color-text-4, #666);
  text-align: right;
  user-select: none;
}

.diff-marker {
  min-width: 20px;
  text-align: center;
  font-weight: bold;
}

.diff-line.deleted .diff-marker {
  color: #d03050;
}

.diff-line.added .diff-marker {
  color: #18a058;
}

.diff-text {
  flex: 1;
  margin: 0;
  padding: 0 8px;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--color-text-2, #ccc);
}

/* Diff 头部横幅 */
.diff-header-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(32, 128, 240, 0.15);
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--color-text-2, #ccc);
}

/* 推理内容提示 */
.reasoning-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(32, 128, 240, 0.15);
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--color-text-2, #ccc);
}

.reasoning-info {
  text-align: center;
  line-height: 1.6;
}

.reasoning-info strong {
  color: #2080f0;
  font-weight: 600;
}
</style>

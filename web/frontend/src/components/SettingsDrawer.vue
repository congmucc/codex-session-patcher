<template>
  <n-drawer v-model:show="show" :width="420" placement="right">
    <n-drawer-content title="设置" closable>
      <n-space vertical size="large">
        <!-- 基础清理配置 -->
        <div class="settings-section">
          <div class="section-title">基础清理</div>
          <div class="section-desc">未启用 AI 时，检测到拒绝回复将替换为以下固定文本</div>

          <n-form-item label="默认替换文本">
            <n-input
              v-model:value="settingsStore.mockResponse"
              type="textarea"
              :rows="3"
              placeholder="替换拒绝内容后的回复文本"
              @update:value="settingsStore.markChanged"
            />
          </n-form-item>
        </div>

        <!-- AI 智能改写 -->
        <div class="settings-section">
          <div class="section-title">
            AI 智能改写
            <n-tag size="small" :type="settingsStore.aiEnabled ? 'success' : 'default'" style="margin-left: 8px">
              {{ settingsStore.aiEnabled ? '已启用' : '未启用' }}
            </n-tag>
          </div>
          <div class="section-desc">启用后，AI 将根据对话上下文生成自然的配合性回复，替代固定文本</div>

          <n-form-item label="启用 AI 改写">
            <n-switch
              v-model:value="settingsStore.aiEnabled"
              @update:value="settingsStore.markChanged"
            />
          </n-form-item>

          <n-collapse-transition :show="settingsStore.aiEnabled">
            <n-form-item label="API Endpoint">
              <n-input
                v-model:value="settingsStore.aiEndpoint"
                placeholder="https://api.openai.com/v1"
                @update:value="settingsStore.markChanged"
              />
              <template #feedback>
                <span class="form-hint">支持 OpenAI 兼容接口（OpenAI / Ollama / OpenRouter 等）</span>
              </template>
            </n-form-item>

            <n-form-item label="API Key">
              <n-input
                v-model:value="settingsStore.aiKey"
                type="password"
                show-password-on="click"
                placeholder="sk-..."
                @update:value="settingsStore.markChanged"
              />
              <template #feedback>
                <span class="form-hint">本地模型（如 Ollama）可留空</span>
              </template>
            </n-form-item>

            <n-form-item label="模型名称">
              <n-input
                v-model:value="settingsStore.aiModel"
                placeholder="gpt-4o / deepseek-chat / ..."
                @update:value="settingsStore.markChanged"
              />
            </n-form-item>
          </n-collapse-transition>
        </div>

        <!-- 拒绝检测配置 -->
        <div class="settings-section">
          <div class="section-title">拒绝检测</div>
          <div class="section-desc">以下关键词用于检测 AI 的拒绝回复</div>

          <n-form-item label="内置中文关键词">
            <div class="builtin-keywords">
              <n-tag v-for="kw in builtinZhKeywords" :key="kw" size="small" type="info" :bordered="false">{{ kw }}</n-tag>
            </div>
          </n-form-item>

          <n-form-item label="内置英文关键词">
            <div class="builtin-keywords">
              <n-tag v-for="kw in builtinEnKeywords" :key="kw" size="small" type="info" :bordered="false">{{ kw }}</n-tag>
            </div>
          </n-form-item>

          <n-form-item label="自定义中文关键词">
            <n-dynamic-tags
              v-model:value="zhKeywords"
              @update:value="handleKeywordsChange('zh', $event)"
            />
          </n-form-item>

          <n-form-item label="自定义英文关键词">
            <n-dynamic-tags
              v-model:value="enKeywords"
              @update:value="handleKeywordsChange('en', $event)"
            />
          </n-form-item>
        </div>
      </n-space>

      <template #footer>
        <n-space>
          <n-button @click="handleReset">重置</n-button>
          <n-button
            type="primary"
            :disabled="!settingsStore.changed"
            :loading="settingsStore.loading"
            @click="handleSave"
          >
            保存
          </n-button>
        </n-space>
      </template>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { useSettingsStore } from '../stores/settingsStore'

const props = defineProps({
  show: Boolean
})

const emit = defineEmits(['update:show'])

const message = useMessage()
const settingsStore = useSettingsStore()

// 双向绑定
const show = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val)
})

// 内置关键词（只读展示）
const builtinZhKeywords = [
  '抱歉', '无法', '违反', '不能', '拒绝', '不允许', '禁止',
  '很抱歉', '对不起', '不好意思', '我无法', '我不能'
]
const builtinEnKeywords = [
  'sorry', 'cannot', 'apologize', 'violate', 'policy',
  'as an AI', 'I cannot', "I'm unable", 'not able to',
  'against my', "I won't", 'refuse to', 'unable to',
  'I apologize', 'not permitted', 'not allowed'
]

// 自定义关键词数组
const zhKeywords = computed({
  get: () => settingsStore.customKeywords.zh || [],
  set: () => {}
})

const enKeywords = computed({
  get: () => settingsStore.customKeywords.en || [],
  set: () => {}
})

function handleKeywordsChange(lang, value) {
  settingsStore.customKeywords[lang] = value
  settingsStore.markChanged()
}

// 打开抽屉时加载设置
watch(show, (val) => {
  if (val) {
    settingsStore.loadSettings()
  }
})

async function handleSave() {
  try {
    await settingsStore.saveSettings()
    message.success('设置已保存')
  } catch (error) {
    message.error('保存失败: ' + error.message)
  }
}

function handleReset() {
  settingsStore.resetSettings()
  message.info('已重置为默认值')
}
</script>

<style scoped>
.settings-section {
  padding: 16px 0;
  border-bottom: 1px solid #3a3a3a;
}

.settings-section:last-child {
  border-bottom: none;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
}

.section-desc {
  font-size: 12px;
  color: #888;
  margin-bottom: 16px;
  line-height: 1.5;
}

.form-hint {
  font-size: 11px;
  color: #666;
}

.builtin-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>

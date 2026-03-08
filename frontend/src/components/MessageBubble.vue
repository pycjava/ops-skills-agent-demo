<script setup lang="ts">
import { computed, ref } from 'vue'
import { marked } from 'marked'
import type { ArtifactKind, ChatMessage } from '../stores/chat'
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()

const props = defineProps<{
  message: ChatMessage
}>()

marked.setOptions({ breaks: true, gfm: true })

const renderedContent = computed(() => {
  if (props.message.type === 'tool_result') {
    const content = props.message.content || ''
    return marked.parse(`\`\`\`text\n${content}\n\`\`\``) as string
  }

  const raw = props.message.content || ''
  if (props.message.streaming) {
    return raw
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '<br/>')
  }

  return marked.parse(raw) as string
})

const toolInputJson = computed(() => {
  if (props.message.type === 'tool_call' && props.message.toolInput) {
    return JSON.stringify(props.message.toolInput, null, 2)
  }
  return ''
})

const isUser = computed(() => props.message.role === 'user' && props.message.type === 'text')
const isAssistant = computed(
  () => props.message.role === 'assistant' && props.message.type === 'text',
)
const isToolCall = computed(() => props.message.type === 'tool_call')
const isToolResult = computed(() => props.message.type === 'tool_result')
const isError = computed(() => props.message.type === 'error')

const showThinking = ref(false)
const showSystemContent = ref(false)

const toolLabel = computed(() => {
  if (props.message.type === 'tool_call') return props.message.toolName || '工具调用'
  if (props.message.type === 'tool_result') return props.message.toolName || '工具结果'
  return ''
})

const metaLabel = computed(() => {
  if (isToolCall.value) return '工具调用'
  if (isToolResult.value) return '工具结果'
  if (isError.value) return '系统提示'
  return '系统消息'
})

const formattedTime = computed(() => {
  if (!props.message.timestamp) return ''
  return new Date(props.message.timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
})

function guessMimeType(path: string) {
  const normalized = path.toLowerCase()

  if (normalized.endsWith('.md')) return 'text/markdown;charset=utf-8'
  if (normalized.endsWith('.txt')) return 'text/plain;charset=utf-8'
  if (normalized.endsWith('.json')) return 'application/json;charset=utf-8'
  if (normalized.endsWith('.html')) return 'text/html;charset=utf-8'
  if (normalized.endsWith('.csv')) return 'text/csv;charset=utf-8'

  return 'application/octet-stream'
}

function inferArtifactKind(path: string, artifactKind?: ArtifactKind): ArtifactKind {
  if (artifactKind) return artifactKind

  const normalized = path.toLowerCase()
  if (normalized.startsWith('/memories/')) return 'memory'
  if (
    normalized.endsWith('.md') ||
    normalized.endsWith('.html') ||
    normalized.endsWith('.pdf')
  ) {
    return 'report'
  }

  return 'file'
}

const fileArtifact = computed(() => {
  if (!isToolResult.value) return null
  if (!['write_file', 'edit_file'].includes(props.message.toolName || '')) return null
  if (!props.message.toolInput) return null

  const maybePath = props.message.toolInput.file_path ?? props.message.toolInput.path
  const maybeContent = props.message.toolInput.content
  const path = typeof maybePath === 'string' ? maybePath.trim() : ''
  const content = typeof maybeContent === 'string' ? maybeContent : ''

  if (!path || !content) return null

  const kind = inferArtifactKind(path, props.message.artifactKind)

  return {
    kind,
    path,
    content,
    name: path.split('/').filter(Boolean).pop() || path,
    isDownloadable: kind !== 'memory',
  }
})

function downloadArtifact() {
  if (!fileArtifact.value || !fileArtifact.value.isDownloadable) return

  const blob = new Blob([fileArtifact.value.content], {
    type: guessMimeType(fileArtifact.value.path),
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = fileArtifact.value.name
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

async function openMemoryArtifact() {
  if (!fileArtifact.value || fileArtifact.value.kind !== 'memory') return
  await chatStore.openMemoryDocument(fileArtifact.value.path)
}

function handleArtifactAction() {
  if (!fileArtifact.value) return

  if (fileArtifact.value.kind === 'memory') {
    void openMemoryArtifact()
    return
  }

  downloadArtifact()
}

const toolResultTitle = computed(() => {
  if (!fileArtifact.value) return '查看工具返回结果'
  return fileArtifact.value.kind === 'memory' ? '完成长期记忆写入' : '完成文件创建'
})

const artifactKicker = computed(() => {
  if (!fileArtifact.value) return ''
  if (fileArtifact.value.kind === 'memory') return '长期记忆已保存'
  if (fileArtifact.value.kind === 'report') return '结果报告'
  return '生成文件'
})

const artifactActionLabel = computed(() => {
  if (!fileArtifact.value) return ''
  if (fileArtifact.value.kind === 'memory') return '查看记忆'
  if (fileArtifact.value.kind === 'report') return '下载报告'
  return '下载文件'
})
</script>

<template>
  <div class="msg" :class="[`msg-${message.role}`, `msg-${message.type}`]">
    <div v-if="isUser" class="user-row">
      <div class="user-bubble">
        <div v-html="renderedContent"></div>
      </div>
    </div>

    <article v-else-if="isAssistant" class="assistant-row">
      <div v-if="message.thinking" class="thinking-panel">
        <div class="thinking-header" @click="showThinking = !showThinking">
          <span class="thinking-badge">{{ message.streaming ? '思考中' : '思考过程' }}</span>
          <span class="thinking-toggle">{{ showThinking ? '收起' : '展开' }}</span>
        </div>
        <div v-if="showThinking" class="thinking-body">
          {{ message.thinking }}
        </div>
      </div>

      <div class="assistant-content" v-html="renderedContent"></div>
    </article>

    <div v-else class="system-row">
      <div class="system-meta">
        <span class="system-badge" :class="{ danger: isError }">{{ metaLabel }}</span>
        <span v-if="toolLabel" class="system-tool">{{ toolLabel }}</span>
        <span v-if="formattedTime" class="system-time">{{ formattedTime }}</span>
      </div>

      <div v-if="isToolCall" class="sys-panel">
        <div class="sys-header" @click="showSystemContent = !showSystemContent">
          <span class="sys-title">{{ message.content }}</span>
          <span v-if="message.type === 'tool_call' && chatStore.isLoading" class="spinner"></span>
          <span v-else class="sys-toggle">{{ showSystemContent ? '收起' : '展开' }}</span>
        </div>

        <div v-if="showSystemContent" class="sys-body">
          <pre v-if="toolInputJson"><code>{{ toolInputJson }}</code></pre>
          <span v-else class="sys-empty">无参数</span>
        </div>
      </div>

      <div v-else-if="isToolResult" class="sys-panel sys-panel-result">
        <div class="sys-header" @click="showSystemContent = !showSystemContent">
          <span class="sys-title">{{ toolResultTitle }}</span>
          <span class="sys-toggle">{{ showSystemContent ? '收起' : '展开' }}</span>
        </div>

        <div v-if="fileArtifact" class="artifact-card">
          <div class="artifact-main">
            <span class="artifact-kicker">{{ artifactKicker }}</span>
            <span class="artifact-name">{{ fileArtifact.name }}</span>
            <span class="artifact-path">{{ fileArtifact.path }}</span>
          </div>
          <button type="button" class="artifact-action" @click.stop="handleArtifactAction">
            {{ artifactActionLabel }}
          </button>
        </div>

        <div v-if="showSystemContent" class="sys-body">
          <div v-html="renderedContent"></div>
        </div>
      </div>

      <div v-else class="system-note" :class="{ 'system-note-error': isError }">
        {{ message.content }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.msg {
  width: 100%;
}

.user-row {
  display: flex;
  justify-content: flex-end;
}

.user-bubble {
  max-width: min(100%, 340px);
  padding: 14px 18px;
  border: 1px solid var(--border);
  border-radius: 20px;
  background: var(--bubble-user);
  color: var(--text-strong);
  box-shadow: 0 8px 20px rgba(86, 73, 51, 0.05);
}

.user-bubble :deep(p) {
  margin: 0;
  line-height: 1.7;
  word-break: break-word;
}

.assistant-row {
  width: 100%;
  color: var(--text-strong);
}

.assistant-content {
  font-size: 18px;
  line-height: 1.85;
}

.assistant-content :deep(p) {
  margin: 0 0 16px;
}

.assistant-content :deep(p:last-child) {
  margin-bottom: 0;
}

.assistant-content :deep(ul),
.assistant-content :deep(ol) {
  margin: 14px 0;
  padding-left: 24px;
}

.assistant-content :deep(li) {
  margin-bottom: 8px;
}

.assistant-content :deep(h1),
.assistant-content :deep(h2),
.assistant-content :deep(h3) {
  margin: 24px 0 12px;
  color: var(--text-strong);
  line-height: 1.35;
}

.assistant-content :deep(strong) {
  font-weight: 700;
  color: var(--text-strong);
}

.assistant-content :deep(a) {
  color: var(--accent);
  text-decoration: none;
}

.assistant-content :deep(a:hover) {
  text-decoration: underline;
}

.assistant-content :deep(blockquote) {
  margin: 18px 0;
  padding-left: 18px;
  border-left: 3px solid var(--border-strong);
  color: var(--text-muted);
}

.assistant-content :deep(pre) {
  margin: 18px 0;
  padding: 16px 18px;
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--card-strong);
  font-size: 14px;
  line-height: 1.7;
}

.assistant-content :deep(code) {
  font-family:
    'SFMono-Regular',
    Consolas,
    'Liberation Mono',
    Menlo,
    monospace;
  font-size: 0.92em;
}

.assistant-content :deep(p > code) {
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bg-soft);
  color: var(--text-strong);
}

.assistant-content :deep(table) {
  width: 100%;
  margin: 18px 0;
  border-collapse: collapse;
  overflow: hidden;
  border-radius: 16px;
  font-size: 15px;
}

.assistant-content :deep(th),
.assistant-content :deep(td) {
  padding: 12px 14px;
  border: 1px solid var(--border);
}

.assistant-content :deep(th) {
  background: var(--bg-soft);
  color: var(--text-strong);
}

.thinking-panel {
  margin-bottom: 18px;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.4);
}

[data-theme='dark'] .thinking-panel {
  background: rgba(255, 255, 255, 0.03);
}

.thinking-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 14px;
  cursor: pointer;
}

.thinking-badge {
  color: var(--warning);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.thinking-toggle {
  color: var(--text-muted);
  font-size: 12px;
}

.thinking-body {
  padding: 0 14px 14px;
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
}

.system-row {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.system-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-muted);
  font-size: 12px;
}

.system-badge {
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--bg-soft);
  color: var(--text-muted);
  font-weight: 700;
}

.system-badge.danger {
  background: rgba(200, 111, 100, 0.12);
  color: var(--danger);
}

.system-tool {
  color: var(--text);
  font-weight: 600;
}

.system-time {
  margin-left: auto;
}

.sys-panel,
.system-note {
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.36);
}

[data-theme='dark'] .sys-panel,
[data-theme='dark'] .system-note {
  background: rgba(255, 255, 255, 0.03);
}

.sys-panel-result {
  border-color: rgba(113, 147, 111, 0.26);
}

.sys-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  cursor: pointer;
}

.sys-title {
  flex: 1;
  color: var(--text-strong);
  font-size: 14px;
}

.sys-toggle {
  color: var(--text-muted);
  font-size: 13px;
}

.artifact-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 0 16px 16px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.52);
}

[data-theme='dark'] .artifact-card {
  background: rgba(255, 255, 255, 0.04);
}

.artifact-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.artifact-kicker {
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.artifact-name {
  color: var(--text-strong);
  font-size: 15px;
  font-weight: 700;
  word-break: break-word;
}

.artifact-path {
  color: var(--text-muted);
  font-size: 12px;
  word-break: break-all;
}

.artifact-action {
  flex-shrink: 0;
  padding: 10px 16px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--bg-soft);
  color: var(--text-strong);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease,
    background 0.2s ease;
}

.artifact-action:hover {
  border-color: var(--border-strong);
  transform: translateY(-1px);
}

.sys-body {
  padding: 0 16px 16px;
  color: var(--text);
  font-size: 14px;
  line-height: 1.7;
}

.sys-body pre {
  margin: 0 !important;
  padding: 14px 16px;
  overflow-x: auto;
  border-radius: 14px;
  background: var(--card-strong) !important;
}

.sys-empty {
  color: var(--text-muted);
}

.system-note {
  padding: 14px 16px;
  color: var(--text);
  line-height: 1.7;
}

.system-note-error {
  border-color: rgba(200, 111, 100, 0.28);
  color: var(--danger);
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(139, 115, 255, 0.2);
  border-top-color: var(--accent);
  border-radius: 999px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

<script setup lang="ts">
import { computed, ref } from 'vue'
import DOMPurify from 'dompurify'
import { marked, Renderer } from 'marked'
import type {
  ArtifactKind,
  ChatMessage,
  ConversationAttachmentSnapshot,
} from '../stores/chat'
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()

const emit = defineEmits<{
  (e: 'open-memory', path: string): void
  (e: 'delete-attachment', attachmentId: string): void
}>()

const props = defineProps<{
  message: ChatMessage
}>()

const markdownRenderer = new Renderer()
markdownRenderer.html = ({ text }) => escapeHtml(text)

marked.setOptions({
  breaks: true,
  gfm: true,
  renderer: markdownRenderer,
})

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function sanitizeHtml(value: string): string {
  return DOMPurify.sanitize(value, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: ['iframe', 'script', 'style'],
  })
}

function renderMarkdown(value: string): string {
  return sanitizeHtml(marked.parse(value, { renderer: markdownRenderer }) as string)
}

function renderStreamingText(value: string): string {
  return sanitizeHtml(escapeHtml(value).replace(/\n/g, '<br/>'))
}

function renderMessageContent(message: ChatMessage): string {
  if (message.type === 'tool_result') {
    const content = message.content || ''
    return renderMarkdown(`\`\`\`text\n${content}\n\`\`\``)
  }

  const raw = message.content || ''
  if (message.streaming) {
    return renderStreamingText(raw)
  }

  return renderMarkdown(raw)
}

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
  if (
    normalized.startsWith('/memories/reports/') &&
    (normalized.endsWith('.md') || normalized.endsWith('.html') || normalized.endsWith('.pdf'))
  ) {
    return 'report'
  }
  if (normalized.startsWith('/memories/')) return 'memory'
  if (normalized.endsWith('.md') || normalized.endsWith('.html') || normalized.endsWith('.pdf')) {
    return 'report'
  }

  return 'file'
}

function formatCompactNumber(value: number): string {
  return value.toFixed(2).replace(/\.?0+$/, '')
}

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) {
    return `${sizeBytes}B`
  }

  if (sizeBytes < 1024 * 1024) {
    return `${formatCompactNumber(sizeBytes / 1024)}KB`
  }

  return `${formatCompactNumber(sizeBytes / (1024 * 1024))}MB`
}

function formatAttachmentType(filename: string): string {
  const segments = filename.split('.')
  const extension = segments.length > 1 ? segments[segments.length - 1]?.trim() : ''
  return extension ? extension.toUpperCase() : 'FILE'
}

function isActiveAttachment(attachment: ConversationAttachmentSnapshot): boolean {
  return activeConversationAttachmentIds.value.has(attachment.id)
}

function handleAttachmentDelete(attachmentId: string) {
  emit('delete-attachment', attachmentId)
}

const renderedContent = computed(() => renderMessageContent(props.message))

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
const userAttachments = computed(() => props.message.attachments || [])
const activeConversationAttachmentIds = computed(
  () => new Set(chatStore.conversationAttachments.map((attachment) => attachment.id)),
)

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

function resolveAgentLabel(agentId?: string): string | null {
  const normalizedAgentId = typeof agentId === 'string' ? agentId.trim() : ''
  if (!normalizedAgentId) return null

  const matchingAgent = chatStore.agents.find((agent) => agent.id === normalizedAgentId)
  return matchingAgent?.label || null
}

const messageAgentLabel = computed(() => {
  if (props.message.role === 'user') return null

  if (
    props.message.type === 'tool_call' &&
    props.message.toolName === 'task' &&
    typeof props.message.toolInput?.subagent_type === 'string'
  ) {
    return resolveAgentLabel(props.message.toolInput.subagent_type) || '智能编排助手'
  }

  return resolveAgentLabel(props.message.agentId) || '智能编排助手'
})

const assistantAgentLabel = computed(() =>
  props.message.role === 'assistant' ? messageAgentLabel.value : null,
)

const systemAgentLabel = computed(() =>
  props.message.role === 'system' ? messageAgentLabel.value : null,
)

const formattedTime = computed(() => {
  if (!props.message.timestamp) return ''
  return new Date(props.message.timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
})

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

function handleArtifactAction() {
  if (!fileArtifact.value) return

  if (fileArtifact.value.kind === 'memory') {
    emit('open-memory', fileArtifact.value.path)
    return
  }

  downloadArtifact()
}

const toolResultTitle = computed(() => {
  if (!fileArtifact.value) return '查看工具返回结果'
  if (fileArtifact.value.kind === 'memory') return '完成长期记忆写入'
  if (fileArtifact.value.kind === 'report') return '完成 Skill 报告生成'
  return '完成文件创建'
})

const artifactKicker = computed(() => {
  if (!fileArtifact.value) return ''
  if (fileArtifact.value.kind === 'memory') return '长期记忆已保存'
  if (fileArtifact.value.kind === 'report') return 'Skill 巡检报告'
  return '生成文件'
})

const artifactActionLabel = computed(() => {
  if (!fileArtifact.value) return ''
  if (fileArtifact.value.kind === 'memory') return '查看记忆'
  if (fileArtifact.value.kind === 'report') return '下载 Skill 报告'
  return '下载文件'
})
</script>

<template>
  <div class="msg" :class="[`msg-${message.role}`, `msg-${message.type}`]">
    <div v-if="isUser" class="user-row">
      <div class="user-stack">
        <div v-if="userAttachments.length > 0" class="user-attachment-grid">
          <div
            v-for="attachment in userAttachments"
            :key="attachment.id"
            :data-testid="`message-attachment-${attachment.id}`"
            class="message-attachment-card"
            :class="{ 'message-attachment-card-removed': !isActiveAttachment(attachment) }"
          >
            <div class="message-attachment-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path
                  d="M8 3.75A2.25 2.25 0 0 0 5.75 6v12A2.25 2.25 0 0 0 8 20.25h8A2.25 2.25 0 0 0 18.25 18V8.81a2.25 2.25 0 0 0-.66-1.59l-2.81-2.81a2.25 2.25 0 0 0-1.59-.66H8Z"
                  fill="currentColor"
                  opacity="0.92"
                />
                <path
                  d="M13.25 3.93V7A1.25 1.25 0 0 0 14.5 8.25h3.07"
                  fill="none"
                  stroke="rgba(255, 255, 255, 0.78)"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="1.4"
                />
                <path
                  d="M9.25 11.25h5.5M9.25 14.25h5.5"
                  fill="none"
                  stroke="rgba(255, 255, 255, 0.92)"
                  stroke-linecap="round"
                  stroke-width="1.4"
                />
              </svg>
            </div>

            <div class="message-attachment-copy">
              <span class="message-attachment-name">{{ attachment.original_name }}</span>
              <span class="message-attachment-meta">
                {{ formatAttachmentType(attachment.original_name) }}
                {{ formatFileSize(attachment.size_bytes) }}
              </span>
            </div>

            <button
              v-if="isActiveAttachment(attachment)"
              :data-testid="`message-attachment-delete-${attachment.id}`"
              type="button"
              class="message-attachment-delete"
              :aria-label="`移除附件 ${attachment.original_name}`"
              :title="`移除附件 ${attachment.original_name}`"
              @click="handleAttachmentDelete(attachment.id)"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="m8 8 8 8M16 8l-8 8"
                  fill="none"
                  stroke="currentColor"
                  stroke-linecap="round"
                  stroke-width="1.8"
                />
              </svg>
            </button>

            <span v-else class="message-attachment-status">已移除</span>
          </div>
        </div>

        <div class="user-bubble">
          <div v-html="renderedContent"></div>
        </div>
      </div>
    </div>

    <article v-else-if="isAssistant" class="assistant-row">
      <div class="assistant-meta">
        <span v-if="assistantAgentLabel" class="assistant-agent">{{ assistantAgentLabel }}</span>
        <span v-if="formattedTime" class="assistant-time">{{ formattedTime }}</span>
      </div>

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
        <span v-if="systemAgentLabel" class="system-agent">{{ systemAgentLabel }}</span>
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

.user-stack {
  width: min(100%, 860px);
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 14px;
}

.user-attachment-grid {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(228px, 1fr));
  gap: 12px;
}

.message-attachment-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 20px;
  background: color-mix(in srgb, var(--card) 92%, white 8%);
}

.message-attachment-card-removed {
  opacity: 0.78;
}

.message-attachment-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border-radius: 14px;
  color: #ffffff;
  background: linear-gradient(180deg, rgba(109, 136, 255, 0.98), rgba(77, 113, 255, 0.94));
  box-shadow: 0 10px 22px rgba(72, 104, 255, 0.18);
}

.message-attachment-icon svg {
  width: 24px;
  height: 24px;
}

.message-attachment-copy {
  min-width: 0;
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
}

.message-attachment-name {
  color: var(--text-strong);
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message-attachment-meta {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.4;
}

.message-attachment-delete {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  flex-shrink: 0;
  border: 1px solid var(--border);
  background: var(--card-strong);
  color: var(--text-muted);
  border-radius: 999px;
  cursor: pointer;
  opacity: 0;
  transition:
    opacity 0.15s ease,
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease;
}

.message-attachment-card:hover .message-attachment-delete,
.message-attachment-card:focus-within .message-attachment-delete {
  opacity: 1;
}

.message-attachment-delete:hover {
  border-color: var(--border-strong);
  background: var(--hover);
  color: var(--text-strong);
}

.message-attachment-delete svg {
  width: 14px;
  height: 14px;
}

.message-attachment-status {
  flex-shrink: 0;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--bg-soft);
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
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

.assistant-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  color: var(--text-muted);
  font-size: 12px;
}

.assistant-agent {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(139, 115, 255, 0.12);
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
}

.assistant-time {
  font-size: 12px;
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

.system-agent {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(139, 115, 255, 0.12);
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
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

@media (max-width: 820px) {
  .user-attachment-grid {
    grid-template-columns: 1fr;
  }

  .message-attachment-delete {
    opacity: 1;
  }
}
</style>

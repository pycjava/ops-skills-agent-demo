<script setup lang="ts">
import { ref } from 'vue'
import { MAX_CONVERSATION_ATTACHMENTS } from '../constants/attachments'
import type { ConversationAttachment } from '../stores/chat'

defineOptions({
  name: 'ConversationAttachmentBar',
})

const props = defineProps<{
  attachments: ConversationAttachment[]
  isUploading: boolean
  error: string | null
  disabled: boolean
}>()

const emit = defineEmits<{
  upload: [files: File[]]
  delete: [attachmentId: string]
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const attachmentHint = `支持文本和图片附件，单会话最多 ${MAX_CONVERSATION_ATTACHMENTS} 个附件`

function triggerFileSelect() {
  if (props.disabled || props.isUploading) {
    return
  }

  fileInput.value?.click()
}

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files ? Array.from(input.files) : []
  if (files.length > 0) {
    emit('upload', files)
  }
  input.value = ''
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

defineExpose({
  triggerFileSelect,
})
</script>

<template>
  <div class="attachment-bar attachment-bar-visible">
    <input
      ref="fileInput"
      data-testid="attachment-input"
      class="attachment-input"
      type="file"
      multiple
      accept=".txt,.md,.markdown,.csv,.json,.sql,.log,.png,.jpg,.jpeg,.webp,text/plain,text/markdown,text/csv,application/json,application/sql,application/x-sql,image/png,image/jpeg,image/webp"
      :disabled="disabled || isUploading"
      @change="handleFileChange"
    />

    <p class="attachment-hint">{{ attachmentHint }}</p>
    <p v-if="error" class="attachment-error">{{ error }}</p>

    <div v-if="attachments.length > 0" class="attachment-list">
      <div
        v-for="attachment in attachments"
        :key="attachment.id"
        class="attachment-card"
      >
        <div class="attachment-icon" aria-hidden="true">
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

        <div class="attachment-copy">
          <span class="attachment-name">{{ attachment.original_name }}</span>
          <span class="attachment-meta">
            {{ formatAttachmentType(attachment.original_name) }}
            {{ formatFileSize(attachment.size_bytes) }}
          </span>
        </div>

        <button
          type="button"
          class="attachment-delete-btn"
          :data-testid="`attachment-delete-${attachment.id}`"
          :title="`移除附件 ${attachment.original_name}`"
          :aria-label="`移除附件 ${attachment.original_name}`"
          :disabled="disabled || isUploading"
          @click="emit('delete', attachment.id)"
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
      </div>
    </div>
  </div>
</template>

<style scoped>
.attachment-bar {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.attachment-bar-visible {
  margin-bottom: 12px;
}

.attachment-input {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  border: 0;
  clip: rect(0, 0, 0, 0);
}

.attachment-error {
  margin: 0;
  color: var(--danger);
  font-size: 12px;
}

.attachment-hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.4;
}

.attachment-list {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 4px;
  scrollbar-width: thin;
}

.attachment-card {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 0 0 292px;
  min-width: 0;
  max-width: 100%;
  padding: 14px 16px;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--card) 92%, white 8%);
}

.attachment-icon {
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

.attachment-icon svg {
  width: 24px;
  height: 24px;
}

.attachment-copy {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
}

.attachment-name {
  color: var(--text-strong);
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attachment-meta {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.4;
}

.attachment-delete-btn {
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
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease;
}

.attachment-delete-btn:hover:not(:disabled) {
  border-color: var(--border-strong);
  background: var(--hover);
  color: var(--text-strong);
}

.attachment-delete-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.attachment-delete-btn svg {
  width: 14px;
  height: 14px;
}

@media (max-width: 820px) {
  .attachment-list {
    flex-direction: column;
    overflow-x: visible;
    padding-bottom: 0;
  }

  .attachment-card {
    flex-basis: auto;
    width: 100%;
  }
}
</style>

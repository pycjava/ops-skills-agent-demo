<script setup lang="ts">
import { computed, ref } from 'vue'
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

const supportedTypesLabel = computed(() => 'txt / md / csv / json / sql / log')

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

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`
  }

  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`
  }

  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<template>
  <div class="attachment-bar">
    <input
      ref="fileInput"
      data-testid="attachment-input"
      class="attachment-input"
      type="file"
      accept=".txt,.md,.markdown,.csv,.json,.sql,.log,text/plain,text/markdown,text/csv,application/json,application/sql,application/x-sql"
      :disabled="disabled || isUploading"
      @change="handleFileChange"
    />

    <div class="attachment-toolbar">
      <button
        type="button"
        class="attachment-upload-btn"
        :disabled="disabled || isUploading"
        @click="triggerFileSelect"
      >
        {{ isUploading ? '上传中…' : '上传附件' }}
      </button>
      <span class="attachment-help">支持 {{ supportedTypesLabel }}</span>
    </div>

    <p v-if="error" class="attachment-error">{{ error }}</p>

    <div v-if="attachments.length > 0" class="attachment-list">
      <div
        v-for="attachment in attachments"
        :key="attachment.id"
        class="attachment-chip"
      >
        <div class="attachment-copy">
          <span class="attachment-name">{{ attachment.original_name }}</span>
          <span class="attachment-meta">{{ formatFileSize(attachment.size_bytes) }}</span>
        </div>
        <button
          type="button"
          class="attachment-delete-btn"
          :data-testid="`attachment-delete-${attachment.id}`"
          :disabled="disabled || isUploading"
          @click="emit('delete', attachment.id)"
        >
          移除
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

.attachment-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.attachment-upload-btn,
.attachment-delete-btn {
  border: 1px solid var(--border);
  background: var(--card-strong);
  color: var(--text-strong);
  border-radius: 999px;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease;
}

.attachment-upload-btn {
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
}

.attachment-delete-btn {
  padding: 6px 10px;
  font-size: 12px;
}

.attachment-upload-btn:hover:not(:disabled),
.attachment-delete-btn:hover:not(:disabled) {
  border-color: var(--border-strong);
  background: var(--hover);
}

.attachment-upload-btn:disabled,
.attachment-delete-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.attachment-help {
  font-size: 12px;
  color: var(--text-muted);
}

.attachment-error {
  margin: 0;
  color: var(--danger);
  font-size: 12px;
}

.attachment-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.attachment-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: 100%;
  padding: 10px 12px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--card);
}

.attachment-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.attachment-name {
  color: var(--text-strong);
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attachment-meta {
  color: var(--text-muted);
  font-size: 12px;
}
</style>

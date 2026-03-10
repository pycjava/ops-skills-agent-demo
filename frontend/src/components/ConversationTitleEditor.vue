<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import {
  getConversationTitleError,
  normalizeConversationTitle,
} from '../utils/conversationTitle'

const props = withDefaults(
  defineProps<{
    title: string
    error?: string
    saving?: boolean
  }>(),
  {
    error: '',
    saving: false,
  },
)

const emit = defineEmits<{
  (e: 'save', title: string): void
  (e: 'cancel'): void
}>()

const isEditing = ref(false)
const draftTitle = ref(props.title)
const inputRef = ref<HTMLInputElement | null>(null)

const validationError = computed(() => getConversationTitleError(draftTitle.value))
const hasChanges = computed(
  () => normalizeConversationTitle(draftTitle.value) !== normalizeConversationTitle(props.title),
)
const displayError = computed(() => validationError.value || props.error)
const isSaveDisabled = computed(
  () => Boolean(validationError.value) || props.saving || !hasChanges.value,
)

watch(
  () => props.title,
  (nextTitle) => {
    if (!isEditing.value) {
      draftTitle.value = nextTitle
    }
  },
)

function startEditing() {
  draftTitle.value = props.title
  isEditing.value = true
  nextTick(() => {
    inputRef.value?.focus()
    inputRef.value?.select()
  })
}

function cancelEditing() {
  draftTitle.value = props.title
  isEditing.value = false
  emit('cancel')
}

function saveTitle() {
  const normalizedTitle = normalizeConversationTitle(draftTitle.value)
  if (validationError.value) {
    return
  }

  if (normalizedTitle === normalizeConversationTitle(props.title)) {
    isEditing.value = false
    return
  }

  isEditing.value = false
  emit('save', normalizedTitle)
}

function handleKeyDown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    cancelEditing()
    return
  }

  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    saveTitle()
  }
}
</script>

<template>
  <div class="conversation-title-editor">
    <div v-if="!isEditing" class="title-display-row">
      <h2 class="chat-title">{{ title }}</h2>
      <button
        class="title-action-btn"
        type="button"
        data-testid="edit-title-btn"
        @click="startEditing"
      >
        编辑
      </button>
    </div>

    <div v-else class="title-edit-row">
      <input
        ref="inputRef"
        v-model="draftTitle"
        type="text"
        class="title-input"
        maxlength="200"
        data-testid="title-input"
        @keydown="handleKeyDown"
      />
      <div class="title-actions">
        <button
          class="title-action-btn primary"
          type="button"
          data-testid="save-title-btn"
          :disabled="isSaveDisabled"
          @click="saveTitle"
        >
          {{ saving ? '保存中...' : '保存' }}
        </button>
        <button
          class="title-action-btn"
          type="button"
          data-testid="cancel-title-btn"
          :disabled="saving"
          @click="cancelEditing"
        >
          取消
        </button>
      </div>
    </div>

    <p v-if="displayError" class="title-error" data-testid="title-error">
      {{ displayError }}
    </p>
  </div>
</template>

<style scoped>
.conversation-title-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.title-display-row,
.title-edit-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-display-row {
  min-width: 0;
}

.chat-title {
  margin: 0;
  min-width: 0;
  color: var(--text-strong);
  font-size: clamp(28px, 4vw, 36px);
  font-weight: 700;
  letter-spacing: -0.04em;
}

.title-input {
  flex: 1;
  min-width: 0;
  height: 44px;
  padding: 0 14px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--card-strong);
  color: var(--text-strong);
  outline: none;
  font-size: 16px;
}

.title-input:focus {
  border-color: var(--border-strong);
  box-shadow: 0 0 0 4px rgba(139, 115, 255, 0.08);
}

.title-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.title-action-btn {
  height: 36px;
  padding: 0 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease;
}

.title-action-btn:hover:not(:disabled) {
  border-color: var(--border-strong);
  background: var(--card-strong);
  color: var(--text-strong);
}

.title-action-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.title-action-btn.primary {
  border-color: transparent;
  background: var(--text-strong);
  color: var(--card-strong);
}

.title-error {
  margin: 0;
  color: var(--danger);
  font-size: 13px;
}

@media (max-width: 720px) {
  .title-edit-row {
    flex-direction: column;
    align-items: stretch;
  }

  .title-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>

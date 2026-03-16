<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { CloudContextCandidate } from '../stores/chat'
import { getMysqlCandidateLabel, getMysqlCandidateMeta } from '../utils/mysqlInspection'

const props = defineProps<{
  visible: boolean
  candidates: CloudContextCandidate[]
  pendingMessage: string
}>()

const emit = defineEmits<{
  select: [candidate: CloudContextCandidate]
  cancel: []
}>()

const selectedKey = ref('')

function getCandidateKey(candidate: CloudContextCandidate, index: number): string {
  return candidate.instance_id?.trim() || candidate.instance_name?.trim() || `candidate-${index}`
}

const selectedCandidate = computed(() => {
  const matched = props.candidates.find(
    (candidate, index) => getCandidateKey(candidate, index) === selectedKey.value,
  )
  return matched ?? props.candidates[0] ?? null
})

watch(
  () => [props.visible, props.candidates] as const,
  () => {
    if (!props.visible) return
    selectedKey.value = props.candidates[0] ? getCandidateKey(props.candidates[0], 0) : ''
  },
  { immediate: true, deep: true },
)

function handleConfirm() {
  if (!selectedCandidate.value) return
  emit('select', selectedCandidate.value)
}

function handleCancel() {
  emit('cancel')
}
</script>

<template>
  <transition name="mysql-selector-fade">
    <div
      v-if="visible"
      class="mysql-selector-backdrop"
      @click.self="handleCancel"
    >
      <div class="mysql-selector-modal" role="dialog" aria-modal="true">
        <div class="mysql-selector-head">
          <div>
            <h3 class="mysql-selector-title">选择要巡检的 MySQL</h3>
            <p class="mysql-selector-subtitle">
              记忆中命中了多台候选实例，请先确认本次巡检目标。
            </p>
          </div>
          <button
            class="mysql-selector-close"
            type="button"
            title="关闭选择弹窗"
            @click="handleCancel"
          >
            ✕
          </button>
        </div>

        <div v-if="pendingMessage" class="mysql-selector-request">
          <span class="mysql-selector-request-label">当前请求</span>
          <p class="mysql-selector-request-text">{{ pendingMessage }}</p>
        </div>

        <div class="mysql-selector-list">
          <label
            v-for="(candidate, index) in candidates"
            :key="getCandidateKey(candidate, index)"
            class="mysql-selector-item"
            :class="{ active: selectedKey === getCandidateKey(candidate, index) }"
          >
            <input
              :data-testid="`candidate-radio-${candidate.instance_id || getCandidateKey(candidate, index)}`"
              :value="getCandidateKey(candidate, index)"
              :checked="selectedKey === getCandidateKey(candidate, index)"
              class="mysql-selector-radio"
              type="radio"
              name="mysql-candidate"
              @change="selectedKey = getCandidateKey(candidate, index)"
            />
            <div class="mysql-selector-item-body">
              <div class="mysql-selector-item-title">
                {{ getMysqlCandidateLabel(candidate) }}
              </div>
              <div class="mysql-selector-item-meta">
                {{ getMysqlCandidateMeta(candidate).join(' · ') || '缺少更多实例信息' }}
              </div>
              <div
                v-if="candidate.credential_ref || candidate.credential_status"
                class="mysql-selector-item-note"
              >
                凭证：
                {{ candidate.credential_ref || '未绑定' }}
                <span v-if="candidate.credential_status">
                  · {{ candidate.credential_status }}
                </span>
              </div>
            </div>
          </label>
        </div>

        <div class="mysql-selector-actions">
          <button class="mysql-selector-btn secondary" type="button" @click="handleCancel">
            取消
          </button>
          <button
            data-testid="confirm-selection-btn"
            class="mysql-selector-btn primary"
            type="button"
            :disabled="!selectedCandidate"
            @click="handleConfirm"
          >
            开始巡检
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.mysql-selector-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(20, 20, 24, 0.32);
  backdrop-filter: blur(12px);
}

.mysql-selector-modal {
  width: min(720px, 100%);
  max-height: min(80vh, 720px);
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px;
  border: 1px solid var(--border);
  border-radius: 24px;
  background: var(--card-strong);
  box-shadow: var(--shadow-card);
}

.mysql-selector-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.mysql-selector-title {
  margin: 0;
  color: var(--text-strong);
  font-size: 1.2rem;
}

.mysql-selector-subtitle {
  margin: 8px 0 0;
  color: var(--text-muted);
  font-size: 0.95rem;
  line-height: 1.5;
}

.mysql-selector-close {
  border: 0;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 1.1rem;
}

.mysql-selector-request {
  padding: 14px 16px;
  border-radius: 16px;
  background: var(--selection);
}

.mysql-selector-request-label {
  display: inline-flex;
  margin-bottom: 6px;
  color: var(--text-soft);
  font-size: 0.78rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.mysql-selector-request-text {
  margin: 0;
  color: var(--text);
  line-height: 1.6;
  white-space: pre-wrap;
}

.mysql-selector-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}

.mysql-selector-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 18px;
  cursor: pointer;
  background: var(--card);
  transition:
    border-color 0.18s ease,
    transform 0.18s ease,
    box-shadow 0.18s ease;
}

.mysql-selector-item:hover,
.mysql-selector-item.active {
  border-color: var(--accent);
  box-shadow: 0 10px 26px rgba(0, 0, 0, 0.08);
  transform: translateY(-1px);
}

.mysql-selector-radio {
  margin-top: 4px;
}

.mysql-selector-item-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.mysql-selector-item-title {
  color: var(--text-strong);
  font-weight: 600;
  word-break: break-word;
}

.mysql-selector-item-meta,
.mysql-selector-item-note {
  color: var(--text-muted);
  font-size: 0.92rem;
  line-height: 1.5;
  word-break: break-word;
}

.mysql-selector-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.mysql-selector-btn {
  min-width: 108px;
  padding: 10px 16px;
  border-radius: 12px;
  border: 1px solid var(--border);
  cursor: pointer;
  font: inherit;
}

.mysql-selector-btn.secondary {
  background: transparent;
  color: var(--text);
}

.mysql-selector-btn.primary {
  border-color: transparent;
  background: var(--accent);
  color: white;
}

.mysql-selector-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.mysql-selector-fade-enter-active,
.mysql-selector-fade-leave-active {
  transition: opacity 0.18s ease;
}

.mysql-selector-fade-enter-from,
.mysql-selector-fade-leave-to {
  opacity: 0;
}

@media (max-width: 720px) {
  .mysql-selector-backdrop {
    padding: 14px;
  }

  .mysql-selector-modal {
    padding: 18px;
    border-radius: 20px;
  }

  .mysql-selector-actions {
    flex-direction: column-reverse;
  }

  .mysql-selector-btn {
    width: 100%;
  }
}
</style>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'

import type { InspectionTask, InspectionTaskDraft, InspectionTaskRun } from '../stores/chat'

type TaskDrawerTab = 'tasks' | 'runs' | 'draft'

const props = defineProps<{
  visible: boolean
  tasks: InspectionTask[]
  runs: InspectionTaskRun[]
  draft: InspectionTaskDraft | null
  draftNotice?: string | null
  activeTab: TaskDrawerTab
  isLoading: boolean
  isSaving: boolean
  error: string | null
  canCreateDraft?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'change-tab', tab: TaskDrawerTab): void
  (e: 'open-draft'): void
  (e: 'refresh'): void
  (e: 'trigger', taskId: string): void
  (e: 'toggle', taskId: string, enabled: boolean): void
  (e: 'delete-task', taskId: string): void
  (e: 'open-conversation', run: InspectionTaskRun): void
  (e: 'save-draft', draft: InspectionTaskDraft): void
}>()

const draftForm = reactive<InspectionTaskDraft>({
  source_conversation_id: null,
  name: '',
  agent_id: 'general',
  skill_id: null,
  prompt_template: '',
  target_payload: null,
  schedule_type: 'cron',
  cron_expr: '0 9 * * *',
  enabled: true,
})

const isDraftValid = computed(
  () => draftForm.name.trim() && draftForm.prompt_template.trim() && draftForm.cron_expr.trim(),
)
const taskNameById = computed(() =>
  Object.fromEntries(props.tasks.map((task) => [task.id, task.name])),
)

watch(
  () => props.draft,
  (draft) => {
    if (!draft) return
    Object.assign(draftForm, draft)
  },
  { immediate: true },
)

function formatDateTime(value: string | null) {
  if (!value) return '未设置'
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatStatus(status: string) {
  if (status === 'succeeded') return '成功'
  if (status === 'failed') return '失败'
  if (status === 'running') return '执行中'
  return '空闲'
}

function formatTriggerType(triggerType: string) {
  return triggerType === 'scheduled' ? '定时' : '手动触发'
}

function handleSaveDraft() {
  if (!isDraftValid.value) return
  emit('save-draft', {
    ...draftForm,
    name: draftForm.name.trim(),
    prompt_template: draftForm.prompt_template.trim(),
    cron_expr: draftForm.cron_expr.trim(),
    skill_id: draftForm.skill_id?.trim() || null,
  })
}
</script>

<template>
  <div v-if="visible" class="task-drawer">
    <div class="task-drawer-head">
      <div class="task-drawer-top">
        <div class="task-drawer-copy">
          <h3 class="task-drawer-title">定时任务</h3>
          <p class="task-drawer-subtitle">独立管理巡检任务和执行记录</p>
        </div>

        <div class="task-drawer-actions">
          <button
            data-testid="task-open-draft"
            class="task-head-btn ui-pill-btn"
            type="button"
            :disabled="!canCreateDraft"
            @click="emit('open-draft')"
          >
            创建定时任务
          </button>
          <button class="task-head-btn ui-pill-btn" type="button" @click="emit('refresh')">
            刷新
          </button>
          <button class="task-head-btn ui-pill-btn" type="button" @click="emit('close')">
            关闭
          </button>
        </div>
      </div>

      <div class="task-tabs ui-segmented-tabs">
        <button
          class="task-tab ui-segmented-tab"
          :class="{ active: activeTab === 'tasks' }"
          type="button"
          @click="emit('change-tab', 'tasks')"
        >
          任务列表
        </button>
        <button
          class="task-tab ui-segmented-tab"
          :class="{ active: activeTab === 'runs' }"
          type="button"
          @click="emit('change-tab', 'runs')"
        >
          执行记录
        </button>
        <button
          v-if="draft"
          class="task-tab ui-segmented-tab"
          :class="{ active: activeTab === 'draft' }"
          type="button"
          @click="emit('change-tab', 'draft')"
        >
          任务草稿
        </button>
      </div>
    </div>

    <div v-if="error" class="task-error">{{ error }}</div>

    <div v-if="activeTab === 'tasks'" class="task-body">
      <div v-if="isLoading && tasks.length === 0" class="task-empty">正在加载任务…</div>
      <div v-else-if="tasks.length === 0" class="task-empty">还没有定时任务</div>
      <div v-else class="task-card-list">
        <article v-for="task in tasks" :key="task.id" class="task-card">
          <div class="task-card-head">
            <div class="task-card-copy">
              <div class="task-card-title-row">
                <span class="task-status-chip">{{ formatStatus(task.last_status) }}</span>
                <h4 class="task-card-title">{{ task.name }}</h4>
              </div>
              <p class="task-card-meta">Cron: {{ task.cron_expr }}</p>
              <p class="task-card-meta">下次执行：{{ formatDateTime(task.next_run_at) }}</p>
            </div>

            <button
              :data-testid="`task-toggle-${task.id}`"
              class="task-toggle-btn ui-pill-btn"
              type="button"
              @click="emit('toggle', task.id, !task.enabled)"
            >
              {{ task.enabled ? '停用' : '启用' }}
            </button>
          </div>

          <div class="task-card-actions">
            <button
              :data-testid="`task-trigger-${task.id}`"
              class="task-action-btn ui-pill-btn ui-pill-btn--primary"
              type="button"
              @click="emit('trigger', task.id)"
            >
              手动触发
            </button>
            <button
              :data-testid="`task-delete-${task.id}`"
              class="task-action-btn ui-pill-btn"
              type="button"
              @click="emit('delete-task', task.id)"
            >
              删除
            </button>
          </div>
        </article>
      </div>
    </div>

    <div v-else-if="activeTab === 'runs'" class="task-body">
      <div v-if="isLoading && runs.length === 0" class="task-empty">正在加载执行记录…</div>
      <div v-else-if="runs.length === 0" class="task-empty">还没有执行记录</div>
      <div v-else class="task-run-list">
        <article v-for="run in runs" :key="run.id" class="task-run-card">
          <div class="task-run-row">
            <span class="task-status-chip">{{ formatStatus(run.status) }}</span>
            <span class="task-run-trigger">{{ formatTriggerType(run.trigger_type) }}</span>
            <span class="task-run-time">{{ formatDateTime(run.started_at) }}</span>
          </div>

          <div v-if="taskNameById[run.task_id]" class="task-run-task-name">
            {{ taskNameById[run.task_id] }}
          </div>

          <div v-if="run.error_message" class="task-run-error">{{ run.error_message }}</div>

          <button
            v-if="run.conversation_id"
            class="task-action-btn ui-pill-btn"
            type="button"
            @click="emit('open-conversation', run)"
          >
            打开会话
          </button>
        </article>
      </div>
    </div>

    <div v-else class="task-body">
      <div class="task-form-card">
        <div v-if="draftNotice" class="task-draft-notice">{{ draftNotice }}</div>

        <label class="task-form-field">
          <span class="task-form-label">任务名称</span>
          <input
            v-model="draftForm.name"
            data-testid="task-draft-name"
            class="task-form-input"
            type="text"
          />
        </label>

        <label class="task-form-field">
          <span class="task-form-label">Prompt</span>
          <textarea v-model="draftForm.prompt_template" class="task-form-textarea" rows="5" />
        </label>

        <label class="task-form-field">
          <span class="task-form-label">Cron 表达式</span>
          <input
            v-model="draftForm.cron_expr"
            data-testid="task-draft-cron"
            class="task-form-input"
            type="text"
          />
        </label>

        <label class="task-toggle-field">
          <input v-model="draftForm.enabled" type="checkbox" />
          <span>创建后立即启用</span>
        </label>

        <button
          data-testid="task-draft-save"
          class="task-action-btn ui-pill-btn ui-pill-btn--primary"
          type="button"
          :disabled="!isDraftValid || isSaving"
          @click="handleSaveDraft"
        >
          {{ isSaving ? '保存中…' : '创建任务' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-drawer {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 18px;
  background: var(--card-strong);
}

.task-drawer-head {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin: -18px -18px 0;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border);
}

.task-drawer-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.task-drawer-title {
  margin: 0;
  color: var(--text-strong);
  font-size: 22px;
}

.task-drawer-subtitle {
  margin: 6px 0 0;
  color: var(--text-muted);
  font-size: 13px;
}

.task-drawer-actions,
.task-card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-tabs {
  width: fit-content;
  max-width: 100%;
}

.task-tab {
  font-weight: 500;
}

.task-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding-top: 18px;
}

.task-card-list,
.task-run-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card,
.task-run-card,
.task-form-card {
  border: 1px solid var(--border);
  border-radius: 20px;
  background: var(--card);
  padding: 16px;
}

.task-card-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.task-card-title-row,
.task-run-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.task-run-task-name {
  margin-top: 10px;
  color: var(--text-strong);
  font-size: 14px;
  font-weight: 600;
}

.task-card-title {
  margin: 0;
  color: var(--text-strong);
  font-size: 16px;
}

.task-card-meta,
.task-run-time {
  margin: 6px 0 0;
  color: var(--text-muted);
  font-size: 12px;
}

.task-status-chip {
  display: inline-flex;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--bg-soft);
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
}

.task-run-trigger,
.task-error,
.task-run-error {
  color: var(--danger);
  font-size: 12px;
}

.task-draft-notice {
  padding: 12px 14px;
  border: 1px solid rgba(179, 138, 89, 0.24);
  border-radius: 14px;
  background: rgba(179, 138, 89, 0.08);
  color: var(--warning);
  font-size: 12px;
  line-height: 1.6;
}

.task-action-btn {
  align-self: flex-start;
}

.task-empty {
  display: grid;
  place-items: center;
  height: 100%;
  min-height: 160px;
  color: var(--text-muted);
  text-align: center;
}

.task-form-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.task-form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-form-label {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
}

.task-form-input,
.task-form-textarea {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--card-strong);
  color: var(--text-strong);
  padding: 10px 12px;
}

.task-form-textarea {
  resize: vertical;
}

.task-toggle-field {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text);
}
</style>

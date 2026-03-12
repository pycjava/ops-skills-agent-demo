<script setup lang="ts">
import { ref } from 'vue'

import type { TaskNotification } from '../stores/chat'

const props = defineProps<{
  notifications: TaskNotification[]
  unreadCount: number
  toast: TaskNotification | null
}>()

const emit = defineEmits<{
  (e: 'read', notificationId: string): void
  (e: 'read-all'): void
  (e: 'open-conversation', conversationId: string): void
  (e: 'download-report', notification: TaskNotification): void
  (e: 'dismiss-toast'): void
}>()

const isOpen = ref(false)

function formatTime(value: string | null) {
  if (!value) return '刚刚'
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <div class="task-notification-center">
    <button
      type="button"
      class="icon-btn task-notification-trigger"
      title="打开任务提醒"
      data-testid="open-task-notification-btn"
      @click="isOpen = !isOpen"
    >
      <span aria-hidden="true">🔔</span>
      <span
        v-if="unreadCount > 0"
        class="task-notification-badge"
        data-testid="task-notification-badge"
      >
        {{ unreadCount > 99 ? '99+' : unreadCount }}
      </span>
    </button>

    <div v-if="isOpen" class="task-notification-dropdown">
      <div class="task-notification-head">
        <div>
          <h3 class="task-notification-title">任务提醒</h3>
          <p class="task-notification-subtitle">最近的任务执行结果和报告下载</p>
        </div>
        <button
          type="button"
          class="ui-pill-btn"
          data-testid="task-notification-read-all"
          :disabled="unreadCount === 0"
          @click="emit('read-all')"
        >
          全部已读
        </button>
      </div>

      <div v-if="notifications.length === 0" class="task-notification-empty">还没有任务提醒</div>

      <div v-else class="task-notification-list">
        <article
          v-for="notification in notifications"
          :key="notification.id"
          class="task-notification-card"
          :class="{ unread: !notification.read_at }"
          :data-testid="`task-notification-item-${notification.id}`"
          @click="emit('read', notification.id)"
        >
          <div class="task-notification-meta">
            <span class="task-notification-status">
              {{ notification.status === 'succeeded' ? '成功' : '失败' }}
            </span>
            <span class="task-notification-time">{{ formatTime(notification.created_at) }}</span>
          </div>
          <div class="task-notification-name">{{ notification.title }}</div>
          <div class="task-notification-summary">{{ notification.summary }}</div>
          <div class="task-notification-actions">
            <button
              v-if="notification.conversation_id"
              type="button"
              class="ui-pill-btn"
              :data-testid="`task-notification-open-conversation-${notification.id}`"
              @click.stop="emit('open-conversation', notification.conversation_id)"
            >
              打开会话
            </button>
            <button
              v-if="notification.report_path"
              type="button"
              class="ui-pill-btn ui-pill-btn--primary"
              :data-testid="`task-notification-download-${notification.id}`"
              @click.stop="emit('download-report', notification)"
            >
              下载报告
            </button>
          </div>
        </article>
      </div>
    </div>

    <div v-if="toast" class="task-notification-toast">
      <div class="task-notification-toast-copy">
        <span class="task-notification-toast-kicker">
          {{ toast.status === 'succeeded' ? '定时任务已完成' : '定时任务失败' }}
        </span>
        <strong>{{ toast.title }}</strong>
        <p>{{ toast.summary }}</p>
      </div>
      <div class="task-notification-toast-actions">
        <button
          v-if="toast.conversation_id"
          type="button"
          class="ui-pill-btn"
          @click="emit('open-conversation', toast.conversation_id)"
        >
          打开会话
        </button>
        <button
          v-if="toast.report_path"
          type="button"
          class="ui-pill-btn ui-pill-btn--primary"
          @click="emit('download-report', toast)"
        >
          下载报告
        </button>
        <button
          type="button"
          class="ui-pill-btn"
          data-testid="task-notification-toast-dismiss"
          @click="emit('dismiss-toast')"
        >
          关闭
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-notification-center {
  position: relative;
}

.task-notification-trigger {
  position: relative;
}

.task-notification-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--danger);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
}

.task-notification-dropdown {
  position: absolute;
  top: calc(100% + 12px);
  right: 0;
  width: min(380px, calc(100vw - 32px));
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 20px;
  background: var(--card-strong);
  box-shadow: var(--shadow-soft);
  z-index: 20;
}

.task-notification-head,
.task-notification-actions,
.task-notification-toast-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.task-notification-title {
  margin: 0;
  color: var(--text-strong);
  font-size: 16px;
}

.task-notification-subtitle {
  margin: 4px 0 0;
  color: var(--text-muted);
  font-size: 12px;
}

.task-notification-list {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 420px;
  overflow: auto;
}

.task-notification-card {
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: var(--card);
  cursor: pointer;
}

.task-notification-card.unread {
  border-color: var(--border-strong);
  box-shadow: inset 0 0 0 1px rgba(139, 115, 255, 0.14);
}

.task-notification-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-muted);
  font-size: 12px;
}

.task-notification-status {
  font-weight: 600;
}

.task-notification-name {
  margin-top: 8px;
  color: var(--text-strong);
  font-weight: 700;
}

.task-notification-summary {
  margin-top: 8px;
  color: var(--text);
  font-size: 13px;
  white-space: pre-line;
  line-height: 1.5;
}

.task-notification-actions {
  justify-content: flex-start;
  margin-top: 12px;
  flex-wrap: wrap;
}

.task-notification-empty {
  margin-top: 14px;
  color: var(--text-muted);
  font-size: 13px;
}

.task-notification-toast {
  position: fixed;
  top: 26px;
  right: 26px;
  width: min(360px, calc(100vw - 24px));
  padding: 16px;
  border: 1px solid var(--border-strong);
  border-radius: 18px;
  background: var(--card-strong);
  box-shadow: var(--shadow-soft);
  z-index: 30;
}

.task-notification-toast-copy strong,
.task-notification-toast-copy p {
  display: block;
}

.task-notification-toast-copy strong {
  margin-top: 6px;
  color: var(--text-strong);
}

.task-notification-toast-copy p {
  margin: 8px 0 0;
  color: var(--text);
  white-space: pre-line;
}

.task-notification-toast-kicker {
  color: var(--text-muted);
  font-size: 12px;
}

.task-notification-toast-actions {
  justify-content: flex-start;
  margin-top: 12px;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .task-notification-dropdown {
    right: -8px;
  }

  .task-notification-toast {
    top: auto;
    right: 12px;
    bottom: 12px;
    left: 12px;
    width: auto;
  }
}
</style>

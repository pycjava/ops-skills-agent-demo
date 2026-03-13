import type { Ref } from 'vue'

import { apiFetch, readErrorMessage } from './helpers'
import type { MemoryDocument, TaskNotification } from './types'

interface TaskNotificationDomainDeps {
  backendUrl: string
  taskNotifications: Ref<TaskNotification[]>
  unreadTaskNotificationCount: Ref<number>
  taskNotificationToast: Ref<TaskNotification | null>
  taskNotificationError: Ref<string | null>
  isTaskNotificationLoading: Ref<boolean>
}

function syncUnreadCount(
  taskNotifications: Ref<TaskNotification[]>,
  unreadTaskNotificationCount: Ref<number>,
) {
  unreadTaskNotificationCount.value = taskNotifications.value.filter(
    (notification) => !notification.read_at,
  ).length
}

function replaceNotification(
  taskNotifications: Ref<TaskNotification[]>,
  notification: TaskNotification,
) {
  const existing = taskNotifications.value.filter((item) => item.id !== notification.id)
  taskNotifications.value = [notification, ...existing]
}

function guessMimeType(path: string) {
  const normalized = path.toLowerCase()
  if (normalized.endsWith('.html')) return 'text/html;charset=utf-8'
  if (normalized.endsWith('.pdf')) return 'application/pdf'
  return 'text/markdown;charset=utf-8'
}

export function createTaskNotificationDomain({
  backendUrl,
  taskNotifications,
  unreadTaskNotificationCount,
  taskNotificationToast,
  taskNotificationError,
  isTaskNotificationLoading,
}: TaskNotificationDomainDeps) {
  async function fetchTaskNotifications() {
    isTaskNotificationLoading.value = true
    taskNotificationError.value = null

    try {
      const res = await apiFetch(`${backendUrl}/api/task-notifications`)
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
      }

      const payload = (await res.json()) as {
        items: TaskNotification[]
        unread_count: number
      }
      taskNotifications.value = payload.items
      unreadTaskNotificationCount.value = payload.unread_count
    } catch (error) {
      taskNotificationError.value =
        error instanceof Error ? error.message : '加载提醒失败'
    } finally {
      isTaskNotificationLoading.value = false
    }
  }

  async function markTaskNotificationRead(notificationId: string) {
    taskNotificationError.value = null

    const res = await apiFetch(
      `${backendUrl}/api/task-notifications/${encodeURIComponent(notificationId)}/read`,
      {
        method: 'POST',
      },
    )

    if (!res.ok) {
      taskNotificationError.value = await readErrorMessage(res, `HTTP ${res.status}`)
      return null
    }

    const notification = (await res.json()) as TaskNotification
    taskNotifications.value = taskNotifications.value.map((item) =>
      item.id === notification.id ? notification : item,
    )
    syncUnreadCount(taskNotifications, unreadTaskNotificationCount)
    return notification
  }

  async function markAllTaskNotificationsRead() {
    taskNotificationError.value = null

    const res = await apiFetch(`${backendUrl}/api/task-notifications/read-all`, {
      method: 'POST',
    })

    if (!res.ok) {
      taskNotificationError.value = await readErrorMessage(res, `HTTP ${res.status}`)
      return false
    }

    const readAt = new Date().toISOString()
    taskNotifications.value = taskNotifications.value.map((notification) =>
      notification.read_at ? notification : { ...notification, read_at: readAt },
    )
    unreadTaskNotificationCount.value = 0
    return true
  }

  function handleTaskNotificationEvent(notification: TaskNotification, unreadCount?: number) {
    replaceNotification(taskNotifications, notification)
    unreadTaskNotificationCount.value =
      typeof unreadCount === 'number' ? unreadCount : unreadTaskNotificationCount.value + 1
    taskNotificationToast.value = notification
  }

  function dismissTaskNotificationToast() {
    taskNotificationToast.value = null
  }

  async function downloadTaskNotificationReport(reportPath: string, reportName?: string | null) {
    const normalizedPath = reportPath.trim()
    if (!normalizedPath) return false

    taskNotificationError.value = null
    const res = await apiFetch(
      `${backendUrl}/api/memories/content?path=${encodeURIComponent(normalizedPath)}`,
    )
    if (!res.ok) {
      taskNotificationError.value = await readErrorMessage(res, `HTTP ${res.status}`)
      return false
    }

    const memoryDocument = (await res.json()) as MemoryDocument
    const filename =
      (typeof reportName === 'string' && reportName.trim()) ||
      normalizedPath.split('/').filter(Boolean).pop() ||
      'report.md'

    const blob = new Blob([memoryDocument.content], {
      type: guessMimeType(filename),
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')

    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    return true
  }

  return {
    fetchTaskNotifications,
    markTaskNotificationRead,
    markAllTaskNotificationsRead,
    handleTaskNotificationEvent,
    dismissTaskNotificationToast,
    downloadTaskNotificationReport,
  }
}

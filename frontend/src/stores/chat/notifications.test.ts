import { ref } from 'vue'

import { createTaskNotificationDomain } from './notifications'
import type { TaskNotification } from './types'

function createNotification(overrides: Partial<TaskNotification> = {}): TaskNotification {
  return {
    id: 'notification-1',
    task_id: 'task-1',
    task_run_id: 'run-1',
    conversation_id: 'conv-1',
    status: 'succeeded',
    title: 'Peets Daily Inspection',
    summary: 'Summary line 1\nSummary line 2',
    report_name: 'report-a.md',
    report_path: '/memories/reports/report-a.md',
    read_at: null,
    created_at: '2026-03-12T09:00:00.000',
    ...overrides,
  }
}

describe('createTaskNotificationDomain', () => {
  test('fetches notifications and unread count from the backend', async () => {
    const notifications = ref<TaskNotification[]>([])
    const unreadCount = ref(0)
    const toastNotification = ref<TaskNotification | null>(null)
    const error = ref<string | null>(null)
    const isLoading = ref(false)

    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          items: [createNotification()],
          unread_count: 1,
        }),
      })),
    )

    const domain = createTaskNotificationDomain({
      backendUrl: 'http://localhost:8000',
      taskNotifications: notifications,
      unreadTaskNotificationCount: unreadCount,
      taskNotificationToast: toastNotification,
      taskNotificationError: error,
      isTaskNotificationLoading: isLoading,
    })

    await domain.fetchTaskNotifications()

    expect(notifications.value).toEqual([createNotification()])
    expect(unreadCount.value).toBe(1)
    expect(error.value).toBeNull()
    expect(isLoading.value).toBe(false)
  })

  test('prepends realtime notifications and keeps the toast visible', () => {
    const notifications = ref<TaskNotification[]>([createNotification({ id: 'existing' })])
    const unreadCount = ref(1)
    const toastNotification = ref<TaskNotification | null>(null)
    const error = ref<string | null>(null)
    const isLoading = ref(false)
    const incoming = createNotification({ id: 'incoming', title: 'Nightly report' })

    const domain = createTaskNotificationDomain({
      backendUrl: '',
      taskNotifications: notifications,
      unreadTaskNotificationCount: unreadCount,
      taskNotificationToast: toastNotification,
      taskNotificationError: error,
      isTaskNotificationLoading: isLoading,
    })

    domain.handleTaskNotificationEvent(incoming, 2)

    expect(notifications.value.map((item) => item.id)).toEqual(['incoming', 'existing'])
    expect(unreadCount.value).toBe(2)
    expect(toastNotification.value).toEqual(incoming)

    domain.dismissTaskNotificationToast()
    expect(toastNotification.value).toBeNull()
  })

  test('marks notifications as read and clears unread count after mark-all', async () => {
    const first = createNotification({ id: 'notification-1' })
    const second = createNotification({ id: 'notification-2', conversation_id: 'conv-2' })
    const notifications = ref<TaskNotification[]>([first, second])
    const unreadCount = ref(2)
    const toastNotification = ref<TaskNotification | null>(null)
    const error = ref<string | null>(null)
    const isLoading = ref(false)
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...first, read_at: '2026-03-12T09:05:00.000' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ updated_count: 1 }),
      })

    vi.stubGlobal('fetch', fetchMock)

    const domain = createTaskNotificationDomain({
      backendUrl: 'http://localhost:8000',
      taskNotifications: notifications,
      unreadTaskNotificationCount: unreadCount,
      taskNotificationToast: toastNotification,
      taskNotificationError: error,
      isTaskNotificationLoading: isLoading,
    })

    await domain.markTaskNotificationRead('notification-1')
    await domain.markAllTaskNotificationsRead()

    expect(notifications.value[0]?.read_at).toBe('2026-03-12T09:05:00.000')
    expect(notifications.value[1]?.read_at).not.toBeNull()
    expect(unreadCount.value).toBe(0)
  })
})

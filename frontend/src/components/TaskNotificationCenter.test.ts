import { mount } from '@vue/test-utils'

import TaskNotificationCenter from './TaskNotificationCenter.vue'

const notification = {
  id: 'notification-1',
  task_id: 'task-1',
  task_run_id: 'run-1',
  conversation_id: 'conv-1',
  status: 'succeeded' as const,
  title: 'Peets Daily Inspection',
  summary: 'Summary line 1\nSummary line 2',
  report_name: 'report-a.md',
  report_path: '/memories/reports/report-a.md',
  read_at: null,
  created_at: '2026-03-12T09:00:00.000',
}

describe('TaskNotificationCenter', () => {
  test('shows unread badge, dropdown actions, and toast actions', async () => {
    const wrapper = mount(TaskNotificationCenter, {
      props: {
        notifications: [notification],
        unreadCount: 1,
        toast: notification,
      },
    })

    expect(wrapper.get('[data-testid="task-notification-badge"]').text()).toBe('1')

    await wrapper.get('[data-testid="open-task-notification-btn"]').trigger('click')

    expect(wrapper.text()).toContain('Peets Daily Inspection')
    expect(wrapper.text()).toContain('Summary line 1')

    await wrapper.get('[data-testid="task-notification-item-notification-1"]').trigger('click')
    await wrapper.get('[data-testid="task-notification-open-conversation-notification-1"]').trigger('click')
    await wrapper.get('[data-testid="task-notification-download-notification-1"]').trigger('click')
    await wrapper.get('[data-testid="task-notification-read-all"]').trigger('click')
    await wrapper.get('[data-testid="task-notification-toast-dismiss"]').trigger('click')

    expect(wrapper.emitted('read')).toEqual([['notification-1']])
    expect(wrapper.emitted('open-conversation')).toEqual([['conv-1']])
    expect(wrapper.emitted('download-report')).toEqual([[notification]])
    expect(wrapper.emitted('read-all')).toEqual([[]])
    expect(wrapper.emitted('dismiss-toast')).toEqual([[]])
  })
})

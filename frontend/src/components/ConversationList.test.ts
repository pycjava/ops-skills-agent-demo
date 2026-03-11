import { mount } from '@vue/test-utils'
import { describe, expect, test } from 'vitest'

import ConversationList from './ConversationList.vue'

describe('ConversationList', () => {
  test('shows a scheduled-task badge for task-generated conversations', () => {
    const wrapper = mount(ConversationList, {
      props: {
        conversations: [
          {
            id: 'conv-1',
            title: 'Peets 巡检',
            source: 'task',
            agent_id: 'dba',
            source_task_id: 'task-1',
            source_task_run_id: 'run-1',
            source_task_trigger_type: 'scheduled',
            created_at: '2026-03-11T08:00:00.000',
            updated_at: '2026-03-11T08:30:00.000',
          },
        ],
        currentId: null,
        agentLabels: {
          dba: '数据库助手',
        },
      },
    })

    expect(wrapper.text()).toContain('定时')
  })
})

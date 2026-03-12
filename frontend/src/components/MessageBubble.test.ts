import { mount } from '@vue/test-utils'
import MessageBubble from './MessageBubble.vue'

const chatStoreMock = {
  isLoading: false,
  agents: [
    { id: 'orchestrator', label: '智能编排助手' },
    { id: 'dba', label: '数据库助手' },
    { id: 'ops', label: '运维助手' },
  ],
  conversationAttachments: [
    {
      id: 'att-1',
      conversation_id: 'conv-1',
      original_name: 'report-a.md',
      stored_name: 'report-a.md',
      relative_path: 'data/conversation_attachments/conv-1/report-a.md',
      mime_type: 'text/markdown',
      size_bytes: 120,
      created_at: '2026-03-10T10:00:00.000',
    },
  ],
}

vi.mock('../stores/chat', () => ({
  useChatStore: () => chatStoreMock,
}))

describe('MessageBubble', () => {
  test('shows the executing agent for assistant messages', () => {
    const wrapper = mount(MessageBubble, {
      props: {
        message: {
          id: 'msg-assistant-1',
          role: 'assistant',
          content: '检查完成，发现 2 条慢查询。',
          type: 'text',
          agentId: 'dba',
          timestamp: Date.now(),
        },
      },
    })

    expect(wrapper.get('.assistant-agent').text()).toBe('数据库助手')
  })

  test('shows the actual executing agent for routed task messages', () => {
    const wrapper = mount(MessageBubble, {
      props: {
        message: {
          id: 'msg-task-1',
          role: 'system',
          content: '正在调用 数据库助手...',
          type: 'tool_call',
          toolName: 'task',
          toolInput: {
            subagent_type: 'dba',
          },
          agentId: 'orchestrator',
          timestamp: Date.now(),
        },
      },
    })

    expect(wrapper.get('.system-agent').text()).toBe('数据库助手')
  })

  test('renders user attachment cards above the bubble and exposes delete only for active attachments', async () => {
    const wrapper = mount(MessageBubble, {
      props: {
        message: {
          id: 'msg-1',
          role: 'user',
          content: '帮我合并汇总信息',
          type: 'text',
          timestamp: Date.now(),
          attachments: [
            {
              id: 'att-1',
              original_name: 'report-a.md',
              stored_name: 'report-a.md',
              relative_path: 'data/conversation_attachments/conv-1/report-a.md',
              mime_type: 'text/markdown',
              size_bytes: 120,
              created_at: '2026-03-10T10:00:00.000',
            },
            {
              id: 'att-2',
              original_name: 'report-b.md',
              stored_name: 'report-b.md',
              relative_path: 'data/conversation_attachments/conv-1/report-b.md',
              mime_type: 'text/markdown',
              size_bytes: 240,
              created_at: '2026-03-10T10:01:00.000',
            },
          ],
        },
      },
    })

    expect(wrapper.get('[data-testid="message-attachment-att-1"]').text()).toContain('report-a.md')
    expect(wrapper.get('[data-testid="message-attachment-att-2"]').text()).toContain('report-b.md')
    expect(wrapper.text()).toContain('已移除')

    await wrapper.get('[data-testid="message-attachment-delete-att-1"]').trigger('click')

    expect(wrapper.emitted('delete-attachment')).toEqual([['att-1']])
    expect(wrapper.find('[data-testid="message-attachment-delete-att-2"]').exists()).toBe(false)
  })
})

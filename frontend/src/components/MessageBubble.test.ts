import { mount } from '@vue/test-utils'
import MessageBubble from './MessageBubble.vue'

const chatStoreMock = {
  isLoading: false,
  agents: [
    { id: 'router', label: '智能编排助手' },
    { id: 'supervisor', label: '复杂任务协调器' },
    { id: 'db-runtime', label: '数据库助手' },
    { id: 'ops-runtime', label: '运维助手' },
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
          agentId: 'db-runtime',
          timestamp: Date.now(),
        },
      },
    })

    expect(wrapper.get('.assistant-agent').text()).toBe('数据库助手')
  })

  test('shows the routing agent for routed task messages', () => {
    const wrapper = mount(MessageBubble, {
      props: {
        message: {
          id: 'msg-task-1',
          role: 'system',
          content: 'router 正在调用数据库助手...',
          type: 'tool_call',
          toolName: 'task',
          toolInput: {
            subagent_type: 'db-runtime',
            source_agent_id: 'router',
          },
          agentId: 'router',
          timestamp: Date.now(),
        },
      },
    })

    expect(wrapper.get('.system-agent').text()).toBe('智能编排助手')
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

    await wrapper.get('[data-testid="message-attachment-delete-att-1"]').trigger('click')

    expect(wrapper.emitted('delete-attachment')).toEqual([['att-1']])
    expect(wrapper.find('[data-testid="message-attachment-delete-att-2"]').exists()).toBe(false)
  })

  test('renders assistant image messages inline with the assistant reply body', () => {
    const wrapper = mount(MessageBubble, {
      props: {
        message: {
          id: 'msg-image-1',
          role: 'assistant',
          content: 'Captured the current dashboard state.',
          type: 'image',
          agentId: 'frontend',
          assetUrl: 'http://localhost:8000/api/conversations/conv-1/messages/msg-image-1/asset',
          assetMimeType: 'image/png',
          assetSource: 'agent-browser',
          assetAlt: 'Agent Browser screenshot',
          assetWidth: 1280,
          assetHeight: 720,
          timestamp: Date.now(),
        },
      },
    })

    const image = wrapper.get('[data-testid="assistant-image"]')
    expect(image.attributes('src')).toBe(
      'http://localhost:8000/api/conversations/conv-1/messages/msg-image-1/asset',
    )
    expect(image.attributes('alt')).toBe('Agent Browser screenshot')
    expect(wrapper.get('.assistant-content').text()).toContain(
      'Captured the current dashboard state.',
    )
  })
})

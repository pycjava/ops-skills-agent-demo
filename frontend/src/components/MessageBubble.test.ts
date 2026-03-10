import { mount } from '@vue/test-utils'
import MessageBubble from './MessageBubble.vue'

const chatStoreMock = {
  isLoading: false,
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

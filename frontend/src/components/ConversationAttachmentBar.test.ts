import { mount } from '@vue/test-utils'
import ConversationAttachmentBar from './ConversationAttachmentBar.vue'

describe('ConversationAttachmentBar', () => {
  test('renders uploaded attachments and emits delete requests', async () => {
    const wrapper = mount(ConversationAttachmentBar, {
      props: {
        attachments: [
          {
            id: 'att-1',
            conversation_id: 'conv-1',
            original_name: 'sample.csv',
            stored_name: 'sample-1.csv',
            relative_path: 'data/conversation_attachments/conv-1/sample-1.csv',
            mime_type: 'text/csv',
            size_bytes: 128,
            created_at: '2026-03-10T10:00:00.000',
          },
        ],
        isUploading: false,
        error: null,
        disabled: false,
      },
    })

    expect(wrapper.text()).toContain('sample.csv')

    await wrapper.get('[data-testid="attachment-delete-att-1"]').trigger('click')

    expect(wrapper.emitted('delete')).toEqual([['att-1']])
  })

  test('emits upload when a file is selected', async () => {
    const wrapper = mount(ConversationAttachmentBar, {
      props: {
        attachments: [],
        isUploading: false,
        error: null,
        disabled: false,
      },
    })

    const input = wrapper.get<HTMLInputElement>('[data-testid="attachment-input"]')
    const file = new File(['hello'], 'notes.txt', { type: 'text/plain' })

    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true,
    })

    await input.trigger('change')

    expect(wrapper.emitted('upload')).toEqual([[[file]]])
  })
})

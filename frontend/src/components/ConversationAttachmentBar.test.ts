import { mount } from '@vue/test-utils'
import ConversationAttachmentBar from './ConversationAttachmentBar.vue'

describe('ConversationAttachmentBar', () => {
  test('renders helper copy, compact metadata, and emits delete requests', async () => {
    const wrapper = mount(ConversationAttachmentBar, {
      props: {
        attachments: [
          {
            id: 'att-1',
            conversation_id: 'conv-1',
            original_name: 'peets-prod-cdp-wecom.md',
            stored_name: 'sample-1.md',
            relative_path: 'data/conversation_attachments/conv-1/sample-1.md',
            mime_type: 'text/markdown',
            size_bytes: 8939,
            created_at: '2026-03-10T10:00:00.000',
          },
        ],
        isUploading: false,
        error: null,
        disabled: false,
      },
    })

    expect(wrapper.text()).toContain('支持文本和图片附件')
    expect(wrapper.text()).toContain('peets-prod-cdp-wecom.md')
    expect(wrapper.text()).toContain('MD 8.73KB')
    expect(wrapper.get('[data-testid="attachment-delete-att-1"]').attributes('aria-label')).toBe(
      '移除附件 peets-prod-cdp-wecom.md',
    )

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
    const fileTwo = new File(['world'], 'query.sql', { type: 'application/sql' })

    expect(input.attributes('multiple')).toBeDefined()

    Object.defineProperty(input.element, 'files', {
      value: [file, fileTwo],
      configurable: true,
    })

    await input.trigger('change')

    expect(wrapper.emitted('upload')).toEqual([[[file, fileTwo]]])
  })

  test('accepts image uploads for OCR scenarios', () => {
    const wrapper = mount(ConversationAttachmentBar, {
      props: {
        attachments: [],
        isUploading: false,
        error: null,
        disabled: false,
      },
    })

    const input = wrapper.get<HTMLInputElement>('[data-testid="attachment-input"]')
    expect(input.attributes('accept')).toContain('image/png')
    expect(input.attributes('accept')).toContain('image/jpeg')
    expect(input.attributes('accept')).toContain('image/webp')
  })

  test('exposes file picker trigger for parent composer controls', () => {
    const wrapper = mount(ConversationAttachmentBar, {
      props: {
        attachments: [],
        isUploading: false,
        error: null,
        disabled: false,
      },
    })

    const input = wrapper.get<HTMLInputElement>('[data-testid="attachment-input"]')
    const clickSpy = vi.spyOn(input.element, 'click')
    const exposed = wrapper.vm as unknown as { triggerFileSelect?: () => void }

    expect(typeof exposed.triggerFileSelect).toBe('function')
    exposed.triggerFileSelect?.()

    expect(clickSpy).toHaveBeenCalledTimes(1)
  })
})

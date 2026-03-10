import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ConversationTitleEditor from './ConversationTitleEditor.vue'

describe('ConversationTitleEditor', () => {
  test('enters edit mode and saves a trimmed title', async () => {
    const wrapper = mount(ConversationTitleEditor, {
      props: {
        title: '当前标题',
      },
    })

    await wrapper.get('[data-testid="edit-title-btn"]').trigger('click')
    const input = wrapper.get('[data-testid="title-input"]')
    await input.setValue('  新标题  ')
    await input.trigger('keydown', { key: 'Enter' })

    const emitted = wrapper.emitted('save')
    expect(emitted).toHaveLength(1)
    expect(emitted?.[0]).toEqual(['新标题'])
  })

  test('cancels editing with escape', async () => {
    const wrapper = mount(ConversationTitleEditor, {
      props: {
        title: '当前标题',
      },
    })

    await wrapper.get('[data-testid="edit-title-btn"]').trigger('click')
    const input = wrapper.get('[data-testid="title-input"]')
    await input.setValue('会被取消')
    await input.trigger('keydown', { key: 'Escape' })
    await nextTick()

    expect(wrapper.find('[data-testid="title-input"]').exists()).toBe(false)
    expect(wrapper.emitted('save')).toBeUndefined()
  })

  test('validates blank and overly long titles before save', async () => {
    const wrapper = mount(ConversationTitleEditor, {
      props: {
        title: '当前标题',
      },
    })

    await wrapper.get('[data-testid="edit-title-btn"]').trigger('click')

    const input = wrapper.get('[data-testid="title-input"]')
    await input.setValue('   ')
    expect(wrapper.get('[data-testid="title-error"]').text()).toContain('不能为空')
    expect(wrapper.get('[data-testid="save-title-btn"]').attributes('disabled')).toBeDefined()

    await input.setValue('x'.repeat(201))
    expect(wrapper.get('[data-testid="title-error"]').text()).toContain('200')
    expect(wrapper.get('[data-testid="save-title-btn"]').attributes('disabled')).toBeDefined()
  })
})

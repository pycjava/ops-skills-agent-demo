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

  test('keeps the edit button stable when the title is long', () => {
    const wrapper = mount(ConversationTitleEditor, {
      props: {
        title: '这是一个非常非常非常非常非常非常非常长的标题，用来验证标题区域不会把编辑按钮挤压变形',
      },
    })

    expect(wrapper.get('.conversation-title-editor').classes()).toContain('title-layout-stable')
    expect(wrapper.get('.title-display-row').classes()).toContain('title-row-stable')
    expect(wrapper.get('[data-testid="edit-title-btn"]').classes()).toContain('title-action-btn-stable')
  })

  test('uses the shared pill button class for the edit action', () => {
    const wrapper = mount(ConversationTitleEditor, {
      props: {
        title: '当前标题',
      },
    })

    expect(wrapper.get('[data-testid="edit-title-btn"]').classes()).toContain('ui-pill-btn')
  })
})

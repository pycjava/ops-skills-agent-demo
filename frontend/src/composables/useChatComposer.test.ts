import { computed, defineComponent, h, reactive } from 'vue'
import { mount } from '@vue/test-utils'
import type { Skill } from '../stores/chat'
import { useChatComposer } from './useChatComposer'

function createKeyEvent(key: string, extra: Partial<KeyboardEvent> = {}) {
  return {
    key,
    shiftKey: false,
    isComposing: false,
    preventDefault: vi.fn(),
    stopPropagation: vi.fn(),
    ...extra,
  } as unknown as KeyboardEvent
}

function requireComposer(value: ReturnType<typeof useChatComposer> | null) {
  if (!value) {
    throw new Error('composer not initialized')
  }

  return value
}

describe('useChatComposer', () => {
  test('matches mention candidates from current input', async () => {
    const sent: Array<{ display: string; send?: string }> = []
    let exposed: ReturnType<typeof useChatComposer> | null = null

    const wrapper = mount(
      defineComponent({
        setup() {
          const state = reactive({
            hasMessages: false,
            isConnected: true,
            isLoading: false,
            skills: [
              { id: 'docker', name: 'Docker', description: '容器工具' },
              { id: 'debugger', name: 'Debugger', description: '调试工具' },
            ] satisfies Skill[],
          })

          exposed = useChatComposer({
            hasMessages: computed(() => state.hasMessages),
            isConnected: computed(() => state.isConnected),
            isLoading: computed(() => state.isLoading),
            skills: computed(() => state.skills),
            sendMessage(display, send) {
              sent.push({ display, send })
            },
          })

          return () => h('div')
        },
      }),
    )

    expect(wrapper.exists()).toBe(true)
    expect(sent).toHaveLength(0)
    const composer = requireComposer(exposed)

    composer.inputText.value = '帮我看看 @do'
    composer.handleInput()

    expect(composer.showMentions.value).toBe(true)
    expect(composer.filteredSkills.value.map((skill: Skill) => skill.id)).toEqual(['docker'])
  })

  test('blocks empty sends and appends system hints for mentioned skills', async () => {
    const sent: Array<{ display: string; send?: string }> = []
    let exposed: ReturnType<typeof useChatComposer> | null = null

    mount(
      defineComponent({
        setup() {
          exposed = useChatComposer({
            hasMessages: computed(() => true),
            isConnected: computed(() => true),
            isLoading: computed(() => false),
            skills: computed(
              () =>
                [
                  { id: 'docker', name: 'Docker', description: '容器工具' },
                  { id: 'shell', name: 'Shell', description: '命令行工具' },
                ] satisfies Skill[],
            ),
            sendMessage(display, send) {
              sent.push({ display, send })
            },
          })

          return () => h('div')
        },
      }),
    )

    const composer = requireComposer(exposed)

    composer.inputText.value = '   '
    composer.handleSend()
    expect(sent).toHaveLength(0)

    composer.inputText.value = '请使用 @docker 处理这个问题'
    composer.handleSend()

    expect(sent).toHaveLength(1)
    expect(sent[0]?.display).toBe('请使用 @docker 处理这个问题')
    expect(sent[0]?.send).toContain('<system_hint>')
    expect(sent[0]?.send).toContain('"docker"')
    expect(composer.inputText.value).toBe('')
    expect(composer.showMentions.value).toBe(false)
  })

  test('handles mention navigation and enter shortcuts', async () => {
    const sent: Array<{ display: string; send?: string }> = []
    let exposed: ReturnType<typeof useChatComposer> | null = null

    mount(
      defineComponent({
        setup() {
          exposed = useChatComposer({
            hasMessages: computed(() => true),
            isConnected: computed(() => true),
            isLoading: computed(() => false),
            skills: computed(
              () =>
                [
                  { id: 'docker', name: 'Docker', description: '容器工具' },
                  { id: 'debugger', name: 'Debugger', description: '调试工具' },
                ] satisfies Skill[],
            ),
            sendMessage(display, send) {
              sent.push({ display, send })
            },
          })

          return () => h('div')
        },
      }),
    )

    const composer = requireComposer(exposed)

    composer.inputText.value = '@d'
    composer.handleInput()

    const arrowDownEvent = createKeyEvent('ArrowDown')
    composer.handleKeyDown(arrowDownEvent)
    expect(arrowDownEvent.preventDefault).toHaveBeenCalled()
    expect(composer.mentionIndex.value).toBe(1)

    const enterMentionEvent = createKeyEvent('Enter')
    composer.handleKeyDown(enterMentionEvent)
    expect(enterMentionEvent.preventDefault).toHaveBeenCalled()
    expect(composer.inputText.value).toBe('@debugger ')
    expect(sent).toHaveLength(0)

    composer.inputText.value = '直接发送'
    const enterSendEvent = createKeyEvent('Enter')
    composer.handleKeyDown(enterSendEvent)
    expect(enterSendEvent.preventDefault).toHaveBeenCalled()
    expect(sent).toHaveLength(1)
    expect(sent[0]?.display).toBe('直接发送')
  })
})

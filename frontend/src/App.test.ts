import { mount } from '@vue/test-utils'
import { computed, ref } from 'vue'
import App from './App.vue'

const chatStoreMock = {
  messages: [] as Array<{ role: string; content: string }>,
  agents: [
    { id: 'general', label: '通用助手' },
    { id: 'dba', label: '数据库助手' },
    { id: 'ops', label: '运维助手' },
    { id: 'extra', label: '额外助手' },
  ],
  activeAgentId: 'dba',
  activeAgent: { id: 'dba', label: '数据库助手' },
  conversations: [],
  currentConversationId: null as string | null,
  draftAgentId: 'dba',
  isConnected: true,
  isLoading: false,
  skills: [],
  mcpServers: [],
  memoryTree: [],
  selectedMemoryPath: null as string | null,
  memoryContent: null,
  memoryError: null as string | null,
  isMemoryLoading: false,
  sendMessage: vi.fn(),
  resolveCloudRequestContext: vi.fn(async () => ({
    matched: false,
    ambiguous: false,
    provider: 'volcengine',
    message: '',
    candidates: [],
  })),
  clearChat: vi.fn(),
  abortAgent: vi.fn(),
  setDraftAgent: vi.fn(),
  connect: vi.fn(),
  fetchAgents: vi.fn(async () => {}),
  fetchConversations: vi.fn(async () => {}),
  fetchSkills: vi.fn(async () => {}),
  fetchMcpServers: vi.fn(async () => {}),
  fetchMemoryTree: vi.fn(async () => {}),
  openMemoryDocument: vi.fn(async () => {}),
  openMemoryContent: vi.fn(async () => {}),
  fetchMemoryContent: vi.fn(async () => {}),
  deleteMemoryFile: vi.fn(async () => {}),
  switchConversation: vi.fn(),
  createConversation: vi.fn(),
  deleteConversation: vi.fn(),
  updateConversationTitle: vi.fn(async () => {}),
}

vi.mock('./stores/chat', () => ({
  useChatStore: () => chatStoreMock,
}))

vi.mock('./composables/useChatComposer', () => ({
  useChatComposer: () => ({
    inputText: ref(''),
    composerInput: ref<HTMLTextAreaElement | null>(null),
    showMentions: ref(false),
    mentionIndex: ref(0),
    filteredSkills: computed(() => []),
    inputPlaceholder: computed(() => '给我发消息或布置任务'),
    clearInput: vi.fn(),
    handleInput: vi.fn(),
    handleKeyDown: vi.fn(),
    handleSend: vi.fn(),
    selectMention: vi.fn(),
    sendQuickPrompt: vi.fn(),
    resizeComposerInput: vi.fn(),
  }),
}))

vi.mock('./composables/useAppChrome', () => ({
  useAppChrome: () => ({
    showSidebar: ref(true),
    isDark: ref(false),
    showInspector: ref(false),
    showAgentOverflowMenu: ref(false),
    rightPanelTab: ref<'skills' | 'mcp' | 'memory'>('skills'),
    heroTitle: computed(() => '工作日愉快，工作的事交给我'),
    agentSelector: ref<HTMLElement | null>(null),
    agentSelectorWrap: ref<HTMLElement | null>(null),
    moreMeasureRef: ref<HTMLElement | null>(null),
    visibleAgents: computed(() => chatStoreMock.agents.slice(0, 3)),
    overflowAgents: computed(() => chatStoreMock.agents.slice(3)),
    setAgentMeasureRef: vi.fn(),
    toggleAgentOverflowMenu: vi.fn(),
    selectAgent: vi.fn(),
    openInspector: vi.fn(),
    closeInspector: vi.fn(),
    handleOpenMemory: vi.fn(),
    toggleTheme: vi.fn(),
  }),
}))

describe('App', () => {
  test('renders readable Chinese labels and stable toolbar icons', () => {
    const wrapper = mount(App, {
      shallow: true,
    })

    const sidebarToggle = wrapper.get('.sidebar-brand .icon-btn')
    expect(sidebarToggle.attributes('title')).toBe('收起侧栏')
    expect(sidebarToggle.text()).toBe('‹')

    const toolbarButtons = wrapper.findAll('.toolbar-right .icon-btn')
    expect(toolbarButtons).toHaveLength(3)
    expect(toolbarButtons[0]?.attributes('title')).toBe('清空当前对话')
    expect(toolbarButtons[0]?.text()).toBe('⌫')
    expect(toolbarButtons[1]?.attributes('title')).toBe('切换深色模式')
    expect(toolbarButtons[2]?.attributes('title')).toBe('打开右侧面板')
    expect(toolbarButtons[2]?.text()).toBe('☷')

    expect(wrapper.text()).toContain('Shift + Enter 换行')
    expect(wrapper.text()).toContain('更多')
    expect(wrapper.find('.send-btn').text()).toBe('→')
  })
})

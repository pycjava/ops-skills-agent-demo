import { flushPromises, mount } from '@vue/test-utils'
import { computed, ref } from 'vue'
import App from './App.vue'
import type { CloudContextResolution } from './stores/chat'

const composerHarness = vi.hoisted(() => ({
  sendMessage:
    null as null | ((displayContent: string, sendContent?: string) => unknown),
  clearInput: vi.fn(),
}))

function createCloudResolution(
  overrides: Partial<CloudContextResolution> = {},
): CloudContextResolution {
  return {
    matched: false,
    ambiguous: false,
    selection_required: false,
    provider: 'volcengine',
    message: '',
    candidates: [],
    ...overrides,
  }
}

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
  conversationAttachments: [] as Array<{
    id: string
    conversation_id: string
    original_name: string
    stored_name: string
    relative_path: string
    mime_type: string
    size_bytes: number
    created_at: string
  }>,
  attachmentError: null as string | null,
  isAttachmentUploading: false,
  sendMessage: vi.fn(),
  uploadConversationAttachment: vi.fn(async (): Promise<boolean> => true),
  deleteConversationAttachment: vi.fn(async () => {}),
  fetchConversationAttachments: vi.fn(async () => {}),
  resolveCloudRequestContext: vi.fn(
    async (): Promise<CloudContextResolution> => createCloudResolution(),
  ),
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
  useChatComposer: (options: {
    sendMessage: (displayContent: string, sendContent?: string) => unknown
  }) => {
    composerHarness.sendMessage = options.sendMessage

    return {
      inputText: ref(''),
      composerInput: ref<HTMLTextAreaElement | null>(null),
      showMentions: ref(false),
      mentionIndex: ref(0),
      filteredSkills: computed(() => []),
      inputPlaceholder: computed(() => '给我发消息或布置任务'),
      clearInput: composerHarness.clearInput,
      handleInput: vi.fn(),
      handleKeyDown: vi.fn(),
      handleSend: vi.fn(),
      selectMention: vi.fn(),
      sendQuickPrompt: vi.fn(),
      resizeComposerInput: vi.fn(),
    }
  },
}))

vi.mock('./composables/useAppChrome', () => ({
  useAppChrome: () => ({
    showSidebar: ref(true),
    isDark: ref(false),
    showInspector: ref(false),
    showAgentOverflowMenu: ref(false),
    rightPanelTab: ref<'skills' | 'mcp' | 'memory'>('skills'),
    heroTitle: computed(() => '工作愉快，工作的事交给我'),
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
  beforeEach(() => {
    vi.clearAllMocks()
    chatStoreMock.uploadConversationAttachment.mockReset()
    chatStoreMock.uploadConversationAttachment.mockImplementation(async (): Promise<boolean> => true)
    composerHarness.sendMessage = null
    chatStoreMock.activeAgentId = 'dba'
    chatStoreMock.messages = []
    chatStoreMock.conversationAttachments = []
    chatStoreMock.attachmentError = null
    chatStoreMock.resolveCloudRequestContext.mockResolvedValue(createCloudResolution())
  })

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

  test('renders upload trigger beside send button in the composer footer', () => {
    const wrapper = mount(App, {
      shallow: true,
    })

    const footer = wrapper.get('.composer-footer')
    const actionButtons = footer.get('.composer-actions').findAll('button')

    expect(wrapper.find('[data-testid="composer-upload-trigger"]').exists()).toBe(true)
    expect(actionButtons).toHaveLength(2)
    expect(actionButtons[0]?.attributes('data-testid')).toBe('composer-upload-trigger')
    expect(actionButtons[1]?.classes()).toContain('send-btn')
  })

  test('falls back to agent chat when cloud resolution does not require selection', async () => {
    mount(App, {
      shallow: true,
    })
    chatStoreMock.resolveCloudRequestContext.mockResolvedValueOnce(
      createCloudResolution({
        ambiguous: true,
        message: '记忆中未命中实例',
        candidates: [
          {
            instance_id: 'mysql-1',
            instance_name: 'peets-prod-pos-mysql',
          },
          {
            instance_id: 'mysql-2',
            instance_name: 'peets-prod-member-mysql',
          },
        ],
      }),
    )

    const sendMessage = composerHarness.sendMessage
    if (!sendMessage) {
      throw new Error('composer sendMessage was not captured')
    }

    const result = await sendMessage('我要进行灵工 mysql 巡检', '我要进行灵工 mysql 巡检')

    expect(result).toBe(true)
    expect(chatStoreMock.resolveCloudRequestContext).toHaveBeenCalledWith(
      '我要进行灵工 mysql 巡检',
    )
    expect(chatStoreMock.sendMessage).toHaveBeenCalledWith(
      '我要进行灵工 mysql 巡检',
      '我要进行灵工 mysql 巡检',
    )
  })

  test('opens mysql selection dialog only when cloud resolution requires it', async () => {
    const wrapper = mount(App, {
      shallow: true,
    })
    chatStoreMock.resolveCloudRequestContext.mockResolvedValueOnce(
      createCloudResolution({
        ambiguous: true,
        selection_required: true,
        message: '命中多个实例候选，请确认',
        candidates: [
          {
            instance_id: 'mysql-1',
            instance_name: 'peets-prod-pos-mysql',
          },
          {
            instance_id: 'mysql-2',
            instance_name: 'peets-prod-member-mysql',
          },
        ],
      }),
    )

    const sendMessage = composerHarness.sendMessage
    if (!sendMessage) {
      throw new Error('composer sendMessage was not captured')
    }

    const result = await sendMessage('我要进行 peets mysql 巡检', '我要进行 peets mysql 巡检')

    expect(result).toBe(false)
    expect(chatStoreMock.sendMessage).not.toHaveBeenCalled()
    expect(
      wrapper.findComponent({ name: 'MysqlInstanceSelectorDialog' }).props('visible'),
    ).toBe(true)
  })

  test('renders attachment bar and forwards upload and delete actions', async () => {
    const file = new File(['notes'], 'notes.txt', { type: 'text/plain' })
    chatStoreMock.conversationAttachments = [
      {
        id: 'att-1',
        conversation_id: 'conv-1',
        original_name: 'notes.txt',
        stored_name: 'notes-1.txt',
        relative_path: 'data/conversation_attachments/conv-1/notes-1.txt',
        mime_type: 'text/plain',
        size_bytes: 5,
        created_at: '2026-03-10T10:00:00.000',
      },
    ]

    const wrapper = mount(App, {
      shallow: true,
    })
    const attachmentBar = wrapper.findComponent({ name: 'ConversationAttachmentBar' })

    expect(attachmentBar.exists()).toBe(true)
    expect(attachmentBar.props('attachments')).toEqual(chatStoreMock.conversationAttachments)

    attachmentBar.vm.$emit('upload', [file])
    attachmentBar.vm.$emit('delete', 'att-1')

    await wrapper.vm.$nextTick()

    expect(chatStoreMock.uploadConversationAttachment).toHaveBeenCalledWith(file)
    expect(chatStoreMock.deleteConversationAttachment).toHaveBeenCalledWith('att-1')
  })

  test('continues uploading remaining files when one file in a batch fails', async () => {
    const files = [
      new File(['one'], 'one.txt', { type: 'text/plain' }),
      new File(['two'], 'two.txt', { type: 'text/plain' }),
      new File(['three'], 'three.txt', { type: 'text/plain' }),
    ]
    chatStoreMock.uploadConversationAttachment
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce(false)
      .mockResolvedValueOnce(true)

    const wrapper = mount(App, {
      shallow: true,
    })
    const attachmentBar = wrapper.findComponent({ name: 'ConversationAttachmentBar' })

    attachmentBar.vm.$emit('upload', files)

    await flushPromises()

    expect(chatStoreMock.uploadConversationAttachment).toHaveBeenNthCalledWith(1, files[0])
    expect(chatStoreMock.uploadConversationAttachment).toHaveBeenNthCalledWith(2, files[1])
    expect(chatStoreMock.uploadConversationAttachment).toHaveBeenNthCalledWith(3, files[2])
    expect(chatStoreMock.attachmentError).toBe('3 个文件中 1 个上传失败')
  })

  test('blocks upload when the conversation already has fifty attachments', async () => {
    chatStoreMock.conversationAttachments = Array.from({ length: 50 }, (_, index) => ({
      id: `att-${index}`,
      conversation_id: 'conv-1',
      original_name: `notes-${index}.txt`,
      stored_name: `notes-${index}.txt`,
      relative_path: `data/conversation_attachments/conv-1/notes-${index}.txt`,
      mime_type: 'text/plain',
      size_bytes: 5,
      created_at: '2026-03-10T10:00:00.000',
    }))

    const wrapper = mount(App, {
      shallow: true,
    })
    const attachmentBar = wrapper.findComponent({ name: 'ConversationAttachmentBar' })

    attachmentBar.vm.$emit('upload', [new File(['extra'], 'overflow.txt', { type: 'text/plain' })])

    await flushPromises()

    expect(chatStoreMock.uploadConversationAttachment).not.toHaveBeenCalled()
    expect(chatStoreMock.attachmentError).toBe('当前会话最多 50 个附件')
  })

  test('blocks the whole batch when selected files exceed the remaining slots', async () => {
    chatStoreMock.conversationAttachments = Array.from({ length: 48 }, (_, index) => ({
      id: `att-${index}`,
      conversation_id: 'conv-1',
      original_name: `notes-${index}.txt`,
      stored_name: `notes-${index}.txt`,
      relative_path: `data/conversation_attachments/conv-1/notes-${index}.txt`,
      mime_type: 'text/plain',
      size_bytes: 5,
      created_at: '2026-03-10T10:00:00.000',
    }))
    const files = [
      new File(['one'], 'one.txt', { type: 'text/plain' }),
      new File(['two'], 'two.txt', { type: 'text/plain' }),
      new File(['three'], 'three.txt', { type: 'text/plain' }),
    ]

    const wrapper = mount(App, {
      shallow: true,
    })
    const attachmentBar = wrapper.findComponent({ name: 'ConversationAttachmentBar' })

    attachmentBar.vm.$emit('upload', files)

    await flushPromises()

    expect(chatStoreMock.uploadConversationAttachment).not.toHaveBeenCalled()
    expect(chatStoreMock.attachmentError).toBe('当前会话最多 50 个附件，还可上传 2 个')
  })
})

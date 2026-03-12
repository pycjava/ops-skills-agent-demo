import { flushPromises, mount } from '@vue/test-utils'
import { computed, nextTick, ref } from 'vue'

import App from './App.vue'
import type {
  CloudContextResolution,
  ConversationItem,
  InspectionTask,
  InspectionTaskDraft,
  InspectionTaskFromConversationMessageResult,
  InspectionTaskRun,
  TaskNotification,
} from './stores/chat'
import type { TaskStreamEvent } from './stores/chat/tasks'

type AppTestMessage = {
  id?: string
  role: string
  content: string
  type?: string
  timestamp?: number
  attachments?: Array<Record<string, unknown>>
  toolName?: string
  toolDesc?: string
  toolInput?: Record<string, unknown>
  agentId?: string
}

const composerHarness = vi.hoisted(() => ({
  sendMessage:
    null as null | ((displayContent: string, sendContent?: string) => unknown),
  clearInput: vi.fn(),
}))

const chromeHarness = vi.hoisted(() => ({
  showInspector: null as null | { value: boolean },
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

function createTaskNotification(
  overrides: Partial<TaskNotification> = {},
): TaskNotification {
  return {
    id: 'notification-1',
    task_id: 'task-1',
    task_run_id: 'run-1',
    conversation_id: 'conv-1',
    status: 'succeeded',
    title: 'Peets Daily Inspection',
    summary: 'Summary line 1\nSummary line 2',
    report_name: 'report-a.md',
    report_path: '/memories/reports/report-a.md',
    read_at: null,
    created_at: '2026-03-12T09:00:00.000',
    ...overrides,
  }
}

const chatStoreMock = {
  messages: [] as AppTestMessage[],
  agents: [
    { id: 'orchestrator', label: '智能编排助手', execution_mode: 'orchestrator' },
    { id: 'general', label: '通用助手' },
    { id: 'dba', label: '数据库助手' },
    { id: 'ops', label: '运维助手' },
    { id: 'extra', label: '额外助手' },
  ],
  activeAgentId: 'orchestrator',
  activeAgent: {
    id: 'orchestrator',
    label: '智能编排助手',
    execution_mode: 'orchestrator',
  },
  conversations: [] as ConversationItem[],
  inspectionTasks: [] as InspectionTask[],
  inspectionTaskRuns: [] as InspectionTaskRun[],
  taskNotifications: [] as TaskNotification[],
  currentConversationId: null as string | null,
  draftAgentId: 'orchestrator',
  isConnected: true,
  isLoading: false,
  skills: [],
  mcpServers: [],
  inspectionTaskError: null as string | null,
  memoryTree: [],
  selectedMemoryPath: null as string | null,
  memoryContent: null,
  memoryError: null as string | null,
  isMemoryLoading: false,
  isInspectionTaskLoading: false,
  unreadTaskNotificationCount: 0,
  taskNotificationToast: null as TaskNotification | null,
  taskNotificationError: null as string | null,
  isTaskNotificationLoading: false,
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
  fetchInspectionTasks: vi.fn(async () => {}),
  fetchInspectionTaskRuns: vi.fn(async () => {}),
  fetchTaskNotifications: vi.fn(async () => {}),
  buildInspectionTaskDraft: vi.fn(async (): Promise<InspectionTaskDraft | null> => null),
  createInspectionTaskFromConversationMessage: vi.fn(
    async (
      _conversationId: string,
      _message: string,
    ): Promise<InspectionTaskFromConversationMessageResult> => ({
      status: 'not_task_creation',
    }),
  ),
  createInspectionTaskFromConversationMessageStream: vi.fn(
    async (
      _conversationId: string,
      _message: string,
      _onEvent: (event: TaskStreamEvent) => void,
      _options?: { original_message?: string },
    ): Promise<InspectionTaskFromConversationMessageResult> => ({
      status: 'not_task_creation',
    }),
  ),
  createInspectionTask: vi.fn(async () => null),
  updateInspectionTask: vi.fn(async () => null),
  deleteInspectionTask: vi.fn(async () => false),
  triggerInspectionTask: vi.fn(async () => null),
  fetchSkills: vi.fn(async () => {}),
  fetchMcpServers: vi.fn(async () => {}),
  fetchMemoryTree: vi.fn(async () => {}),
  openMemoryDocument: vi.fn(async () => {}),
  openMemoryContent: vi.fn(async () => {}),
  fetchMemoryContent: vi.fn(async () => {}),
  deleteMemoryFile: vi.fn(async () => {}),
  markTaskNotificationRead: vi.fn(async () => null),
  markAllTaskNotificationsRead: vi.fn(async () => true),
  dismissTaskNotificationToast: vi.fn(),
  downloadTaskNotificationReport: vi.fn(async () => true),
  switchConversation: vi.fn(),
  streamInspectionTaskRunConversation: vi.fn(async () => {}),
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
    ...(chromeHarness.showInspector = ref(false), {}),
    showSidebar: ref(true),
    isDark: ref(false),
    showInspector: chromeHarness.showInspector,
    showAgentOverflowMenu: ref(false),
    rightPanelTab: ref<'skills' | 'mcp' | 'memory'>('skills'),
    heroTitle: computed(() => '工作愉快，工作的事交给我'),
    agentSelector: ref<HTMLElement | null>(null),
    agentSelectorWrap: ref<HTMLElement | null>(null),
    moreMeasureRef: ref<HTMLElement | null>(null),
    visibleAgents: computed(() => chatStoreMock.agents),
    overflowAgents: computed(() => []),
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
    chromeHarness.showInspector = null
    chatStoreMock.uploadConversationAttachment.mockReset()
    chatStoreMock.uploadConversationAttachment.mockImplementation(async (): Promise<boolean> => true)
    chatStoreMock.buildInspectionTaskDraft.mockReset()
    chatStoreMock.buildInspectionTaskDraft.mockResolvedValue(null)
    chatStoreMock.createInspectionTaskFromConversationMessage.mockReset()
    chatStoreMock.createInspectionTaskFromConversationMessage.mockResolvedValue({
      status: 'not_task_creation',
    })
    chatStoreMock.createInspectionTaskFromConversationMessageStream.mockReset()
    chatStoreMock.createInspectionTaskFromConversationMessageStream.mockResolvedValue({
      status: 'not_task_creation',
    })
    chatStoreMock.deleteInspectionTask.mockReset()
    chatStoreMock.deleteInspectionTask.mockResolvedValue(true)
    composerHarness.sendMessage = null
    chatStoreMock.activeAgentId = 'orchestrator'
    chatStoreMock.activeAgent = {
      id: 'orchestrator',
      label: '智能编排助手',
      execution_mode: 'orchestrator',
    }
    chatStoreMock.currentConversationId = null
    chatStoreMock.draftAgentId = 'orchestrator'
    chatStoreMock.messages = []
    chatStoreMock.conversations = []
    chatStoreMock.inspectionTasks = []
    chatStoreMock.inspectionTaskRuns = []
    chatStoreMock.taskNotifications = []
    chatStoreMock.conversationAttachments = []
    chatStoreMock.attachmentError = null
    chatStoreMock.inspectionTaskError = null
    chatStoreMock.unreadTaskNotificationCount = 0
    chatStoreMock.taskNotificationToast = null
    chatStoreMock.taskNotificationError = null
    chatStoreMock.resolveCloudRequestContext.mockResolvedValue(createCloudResolution())
  })

  test('renders readable toolbar labels and stable icons', () => {
    const wrapper = mount(App, {
      shallow: true,
    })

    const sidebarToggle = wrapper.get('.sidebar-brand .icon-btn')
    expect(sidebarToggle.attributes('title')).toBe('收起侧栏')

    const toolbarButtons = wrapper.findAll('.toolbar-right .icon-btn')
    expect(toolbarButtons).toHaveLength(4)
    expect(toolbarButtons[0]?.attributes('title')).toBe('清空当前对话')
    expect(toolbarButtons[1]?.attributes('title')).toBe('切换深色模式')
    expect(toolbarButtons[2]?.attributes('title')).toBe('打开定时任务')
    expect(toolbarButtons[3]?.attributes('title')).toBe('打开右侧面板')

    expect(wrapper.text()).toContain('Shift + Enter 换行')
    expect(wrapper.text()).toContain('智能编排助手')
    expect(wrapper.find('.agent-selector').exists()).toBe(false)
  })

  test('wires task notification center props and actions through the store', async () => {
    const notification = createTaskNotification()
    chatStoreMock.taskNotifications = [notification]
    chatStoreMock.unreadTaskNotificationCount = 1
    chatStoreMock.taskNotificationToast = notification

    const wrapper = mount(App, {
      shallow: true,
    })

    const notificationCenter = wrapper.findComponent({ name: 'TaskNotificationCenter' })
    expect(notificationCenter.exists()).toBe(true)
    expect(notificationCenter.props('notifications')).toEqual([notification])
    expect(notificationCenter.props('unreadCount')).toBe(1)
    expect(notificationCenter.props('toast')).toEqual(notification)

    notificationCenter.vm.$emit('read', notification.id)
    await flushPromises()
    expect(chatStoreMock.markTaskNotificationRead).toHaveBeenCalledWith(notification.id)

    notificationCenter.vm.$emit('read-all')
    await flushPromises()
    expect(chatStoreMock.markAllTaskNotificationsRead).toHaveBeenCalled()

    notificationCenter.vm.$emit('open-conversation', 'conv-1')
    await flushPromises()
    expect(chatStoreMock.switchConversation).toHaveBeenCalledWith('conv-1')

    notificationCenter.vm.$emit('download-report', notification)
    await flushPromises()
    expect(chatStoreMock.downloadTaskNotificationReport).toHaveBeenCalledWith(
      '/memories/reports/report-a.md',
      'report-a.md',
    )

    notificationCenter.vm.$emit('dismiss-toast')
    expect(chatStoreMock.dismissTaskNotificationToast).toHaveBeenCalled()
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
        message: '候选未命中唯一实例',
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

    expect(result).toBe(true)
    expect(chatStoreMock.resolveCloudRequestContext).toHaveBeenCalledWith('我要进行 peets mysql 巡检')
    expect(chatStoreMock.sendMessage).toHaveBeenCalledWith(
      '我要进行 peets mysql 巡检',
      '我要进行 peets mysql 巡检',
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

  test.skip('creates an inspection task directly from a conversation message', async () => {
    chatStoreMock.currentConversationId = 'conv-1'
    chatStoreMock.createInspectionTaskFromConversationMessage.mockResolvedValueOnce({
      status: 'created',
      intent_analysis: {
        intent_matched: true,
        outcome: 'created',
        cron_expr: '0 9 * * *',
        summary: '已命中定时任务创建意图，识别到调度表达式 0 9 * * *，并已创建任务「Peets Daily Inspection」。',
        reason: null,
      },
      task: {
        id: 'task-1',
        name: 'Peets Daily Inspection',
        source_conversation_id: 'conv-1',
        agent_id: 'dba',
        skill_id: 'volcengine-rds-health-analyzer',
        prompt_template: 'Inspect peets-prod-pos-mysql for slow queries',
        target_payload: { instance_name: 'peets-prod-pos-mysql' },
        schedule_type: 'cron',
        cron_expr: '0 9 * * *',
        enabled: true,
        last_run_at: null,
        next_run_at: '2026-03-11T09:00:00.000',
        last_status: 'idle',
        created_at: '2026-03-11T08:00:00.000',
        updated_at: '2026-03-11T08:00:00.000',
      },
    })

    const wrapper = mount(App, {
      shallow: true,
    })

    const sendMessage = composerHarness.sendMessage
    if (!sendMessage) {
      throw new Error('composer sendMessage was not captured')
    }

    const result = await sendMessage(
      '生成定时任务，每天 9 点执行',
      '生成定时任务，每天 9 点执行',
    )
    await flushPromises()

    expect(result).toBe(false)
    expect(chatStoreMock.createInspectionTaskFromConversationMessage).toHaveBeenCalledWith(
      'conv-1',
      '生成定时任务，每天 9 点执行',
    )
    expect(chatStoreMock.sendMessage).not.toHaveBeenCalled()
    expect(chatStoreMock.messages).toHaveLength(2)
    expect(chatStoreMock.messages[0]).toMatchObject({
      role: 'system',
      type: 'tool_call',
      toolName: 'inspection_task_intent',
    })
    expect(chatStoreMock.messages[1]).toMatchObject({
      role: 'system',
      type: 'tool_result',
      content:
        '已命中定时任务创建意图，识别到调度表达式 0 9 * * *，并已创建任务「Peets Daily Inspection」。',
      toolName: 'inspection_task_intent',
    })
    expect(composerHarness.clearInput).toHaveBeenCalled()
    expect(chatStoreMock.fetchInspectionTasks).toHaveBeenCalled()
    expect(chatStoreMock.fetchInspectionTaskRuns).toHaveBeenCalled()
    expect(wrapper.findComponent({ name: 'TaskDrawer' }).props('activeTab')).toBe('tasks')
  })

  test.skip('continues normal chat when the backend says the message is not task creation', async () => {
    chatStoreMock.currentConversationId = 'conv-1'
    chatStoreMock.createInspectionTaskFromConversationMessage.mockResolvedValueOnce({
      status: 'not_task_creation',
    })

    mount(App, {
      shallow: true,
    })

    const sendMessage = composerHarness.sendMessage
    if (!sendMessage) {
      throw new Error('composer sendMessage was not captured')
    }

    const result = await sendMessage('Inspect peets mysql now', 'Inspect peets mysql now')
    await flushPromises()

    expect(result).toBe(true)
    expect(chatStoreMock.createInspectionTaskFromConversationMessage).toHaveBeenCalledWith(
      'conv-1',
      'Inspect peets mysql now',
    )
    expect(chatStoreMock.sendMessage).toHaveBeenCalledWith(
      'Inspect peets mysql now',
      'Inspect peets mysql now',
    )
    expect(chatStoreMock.messages).toHaveLength(0)
  })

  test.skip('opens task draft with notice when task intent is missing a complete schedule', async () => {
    chatStoreMock.currentConversationId = 'conv-1'
    chatStoreMock.buildInspectionTaskDraft.mockResolvedValueOnce({
      source_conversation_id: 'conv-1',
      name: 'peets mysql 巡检',
      agent_id: 'dba',
      skill_id: null,
      prompt_template: '请巡检 peets mysql 最近 7 天状态',
      target_payload: null,
      schedule_type: 'cron',
      cron_expr: '0 9 * * *',
      enabled: true,
    })
    chatStoreMock.createInspectionTaskFromConversationMessage.mockImplementationOnce(async () => {
      chatStoreMock.inspectionTaskError =
        '未能从当前这句话中识别完整调度时间，请补充执行频率或具体时间。'
      return {
        status: 'error' as const,
        message: chatStoreMock.inspectionTaskError,
        intent_analysis: {
          intent_matched: true,
          outcome: 'error',
          cron_expr: null,
          summary:
            '已命中定时任务创建意图，未完成创建。调度表达式：未识别。 原因：未能从当前这句话中识别完整调度时间，请补充执行频率或具体时间。',
          reason: chatStoreMock.inspectionTaskError,
        },
      }
    })

    const wrapper = mount(App, {
      shallow: true,
    })

    const sendMessage = composerHarness.sendMessage
    if (!sendMessage) {
      throw new Error('composer sendMessage was not captured')
    }

    const result = await sendMessage('生成定时任务，每月一次', '生成定时任务，每月一次')
    await flushPromises()

    expect(result).toBe(false)
    expect(chatStoreMock.sendMessage).not.toHaveBeenCalled()
    expect(chatStoreMock.messages).toHaveLength(2)
    expect(chatStoreMock.messages[0]).toMatchObject({
      role: 'system',
      type: 'tool_call',
      toolName: 'inspection_task_intent',
    })
    expect(chatStoreMock.messages[1]).toMatchObject({
      role: 'system',
      type: 'tool_result',
      content:
        '已命中定时任务创建意图，未完成创建。调度表达式：未识别。 原因：未能从当前这句话中识别完整调度时间，请补充执行频率或具体时间。',
      toolName: 'inspection_task_intent',
    })
    expect(chatStoreMock.buildInspectionTaskDraft).toHaveBeenCalledWith('conv-1')
    expect(composerHarness.clearInput).toHaveBeenCalled()
    expect(wrapper.findComponent({ name: 'TaskDrawer' }).props('activeTab')).toBe('draft')
    expect(wrapper.findComponent({ name: 'TaskDrawer' }).props('draft')).toMatchObject({
      cron_expr: '0 9 * * *',
      prompt_template: '请巡检 peets mysql 最近 7 天状态',
    })
    expect(wrapper.findComponent({ name: 'TaskDrawer' }).props('draftNotice')).toBe(
      '未能从当前这句话中识别完整调度时间，请补充执行频率或具体时间。',
    )
  })

  test('streams task creation events and opens the task drawer on success', async () => {
    chatStoreMock.currentConversationId = 'conv-1'
    chatStoreMock.createInspectionTaskFromConversationMessageStream.mockImplementationOnce(
      async (
        _conversationId: string,
        _message: string,
        onEvent: (event: TaskStreamEvent) => void,
      ): Promise<InspectionTaskFromConversationMessageResult> => {
        onEvent({
          type: 'tool_call',
          tool_name: 'inspection_task_intent',
          tool_desc: 'Running inspection_task_intent',
        })
        onEvent({
          type: 'tool_result',
          tool_name: 'inspection_task_intent',
          result: 'Recognized cron 0 9 * * *',
        })

        return {
          status: 'created',
          intent_analysis: {
            intent_matched: true,
            outcome: 'created',
            cron_expr: '0 9 * * *',
            summary: 'Created task Peets Daily Inspection',
            reason: null,
          },
          task: {
            id: 'task-1',
            name: 'Peets Daily Inspection',
            source_conversation_id: 'conv-1',
            agent_id: 'dba',
            skill_id: 'volcengine-rds-health-analyzer',
            prompt_template: 'Inspect peets-prod-pos-mysql for slow queries',
            target_payload: { instance_name: 'peets-prod-pos-mysql' },
            schedule_type: 'cron',
            cron_expr: '0 9 * * *',
            enabled: true,
            last_run_at: null,
            next_run_at: '2026-03-11T09:00:00.000',
            last_status: 'idle',
            created_at: '2026-03-11T08:00:00.000',
            updated_at: '2026-03-11T08:00:00.000',
          },
        }
      },
    )

    const wrapper = mount(App, {
      shallow: true,
    })

    const sendMessage = composerHarness.sendMessage
    if (!sendMessage) {
      throw new Error('composer sendMessage was not captured')
    }

    const result = await sendMessage(
      'Create scheduled task every day at 09:00',
      'Create scheduled task every day at 09:00',
    )
    await flushPromises()

    expect(result).toBe(false)
    expect(chatStoreMock.createInspectionTaskFromConversationMessageStream).toHaveBeenCalledWith(
      'conv-1',
      'Create scheduled task every day at 09:00',
      expect.any(Function),
    )
    expect(chatStoreMock.sendMessage).not.toHaveBeenCalled()
    expect(
      chatStoreMock.messages.some(
        (message) =>
          message.type === 'tool_call' && message.toolName === 'inspection_task_intent',
      ),
    ).toBe(true)
    expect(
      chatStoreMock.messages.some(
        (message) =>
          message.type === 'tool_result' && message.toolName === 'inspection_task_intent',
      ),
    ).toBe(true)
    expect(chatStoreMock.fetchInspectionTasks).toHaveBeenCalled()
    expect(chatStoreMock.fetchInspectionTaskRuns).toHaveBeenCalled()
    expect(wrapper.findComponent({ name: 'TaskDrawer' }).props('activeTab')).toBe('tasks')
  })

  test('falls back to normal chat when the task stream reports not_task_creation', async () => {
    chatStoreMock.currentConversationId = 'conv-1'
    chatStoreMock.createInspectionTaskFromConversationMessageStream.mockResolvedValueOnce({
      status: 'not_task_creation',
    })

    mount(App, {
      shallow: true,
    })

    const sendMessage = composerHarness.sendMessage
    if (!sendMessage) {
      throw new Error('composer sendMessage was not captured')
    }

    const result = await sendMessage(
      'Create scheduled task but just explain the process',
      'Create scheduled task but just explain the process',
    )
    await flushPromises()

    expect(result).toBe(true)
    expect(chatStoreMock.createInspectionTaskFromConversationMessageStream).toHaveBeenCalledWith(
      'conv-1',
      'Create scheduled task but just explain the process',
      expect.any(Function),
    )
    expect(chatStoreMock.sendMessage).toHaveBeenCalledWith(
      'Create scheduled task but just explain the process',
      'Create scheduled task but just explain the process',
    )
    expect(chatStoreMock.messages[0]).toMatchObject({
      role: 'user',
      content: 'Create scheduled task but just explain the process',
    })
  })

  test('shows clarification feedback when the task stream needs schedule details', async () => {
    chatStoreMock.currentConversationId = 'conv-1'
    chatStoreMock.createInspectionTaskFromConversationMessageStream.mockImplementationOnce(
      async (
        _conversationId: string,
        _message: string,
        onEvent: (event: TaskStreamEvent) => void,
      ): Promise<InspectionTaskFromConversationMessageResult> => {
        onEvent({
          type: 'clarification_needed',
          content: 'Please provide a recurring schedule.',
          original_message: 'Create scheduled task for this conversation',
        })

        return {
          status: 'clarification_needed',
          message: 'Schedule is incomplete.',
          clarification_prompt: 'Please provide a recurring schedule.',
          intent_analysis: {
            intent_matched: true,
            outcome: 'error',
            cron_expr: null,
            summary: 'Schedule is incomplete.',
            reason: 'Schedule is incomplete.',
          },
        }
      },
    )

    mount(App, {
      shallow: true,
    })

    const sendMessage = composerHarness.sendMessage
    if (!sendMessage) {
      throw new Error('composer sendMessage was not captured')
    }

    const result = await sendMessage(
      'Create scheduled task sometime next month',
      'Create scheduled task sometime next month',
    )
    await flushPromises()

    expect(result).toBe(false)
    expect(chatStoreMock.sendMessage).not.toHaveBeenCalled()
    expect(
      chatStoreMock.messages.some(
        (message) => message.role === 'assistant' && message.content.includes('Please provide'),
      ),
    ).toBe(true)
    expect(
      chatStoreMock.messages.some(
        (message) =>
          message.type === 'tool_result' && message.toolName === 'inspection_task_intent',
      ),
    ).toBe(true)
    expect(chatStoreMock.buildInspectionTaskDraft).not.toHaveBeenCalled()
    expect(composerHarness.clearInput).toHaveBeenCalled()
  })

  test('opens the draft tab from the task drawer header create button', async () => {
    chatStoreMock.currentConversationId = 'conv-1'
    const draft: InspectionTaskDraft = {
      source_conversation_id: 'conv-1',
      name: 'Peets Weekly Inspection',
      agent_id: 'dba',
      skill_id: 'volcengine-rds-health-analyzer',
      prompt_template: 'Inspect peets-prod-member-mysql for the last 30 days',
      target_payload: { instance_name: 'peets-prod-member-mysql' },
      schedule_type: 'cron',
      cron_expr: '0 9 * * *',
      enabled: true,
    }
    chatStoreMock.buildInspectionTaskDraft.mockResolvedValueOnce(draft)

    const wrapper = mount(App, {
      shallow: true,
    })

    await wrapper.get('[data-testid="open-task-drawer-btn"]').trigger('click')
    await flushPromises()

    wrapper.findComponent({ name: 'TaskDrawer' }).vm.$emit('open-draft')
    await flushPromises()

    expect(chatStoreMock.buildInspectionTaskDraft).toHaveBeenCalledWith('conv-1')
    expect(wrapper.findComponent({ name: 'TaskDrawer' }).props('activeTab')).toBe('draft')
    expect(wrapper.findComponent({ name: 'TaskDrawer' }).props('draft')).toMatchObject({
      cron_expr: '0 9 * * *',
      prompt_template: 'Inspect peets-prod-member-mysql for the last 30 days',
    })
  })

  test('deletes a task from the drawer and refreshes the list', async () => {
    chatStoreMock.inspectionTasks = [
      {
        id: 'task-1',
        name: 'Peets Daily Inspection',
        source_conversation_id: 'conv-1',
        agent_id: 'dba',
        skill_id: 'volcengine-rds-health-analyzer',
        prompt_template: 'Inspect peets-prod-pos-mysql for the last 7 days',
        target_payload: { instance_name: 'peets-prod-pos-mysql' },
        schedule_type: 'cron',
        cron_expr: '0 9 * * *',
        enabled: true,
        last_run_at: null,
        next_run_at: '2026-03-11T09:00:00.000',
        last_status: 'idle',
        created_at: '2026-03-11T08:00:00.000',
        updated_at: '2026-03-11T08:00:00.000',
      },
    ]

    const wrapper = mount(App, {
      shallow: true,
    })

    await wrapper.get('[data-testid="open-task-drawer-btn"]').trigger('click')
    await flushPromises()

    wrapper.findComponent({ name: 'TaskDrawer' }).vm.$emit('delete-task', 'task-1')
    await flushPromises()

    expect(chatStoreMock.deleteInspectionTask).toHaveBeenCalledWith('task-1')
    expect(chatStoreMock.fetchInspectionTasks).toHaveBeenCalled()
    expect(chatStoreMock.fetchInspectionTaskRuns).toHaveBeenCalled()
  })

  test('opens a task run from the drawer via streamed playback instead of plain history switch', async () => {
    chatStoreMock.inspectionTaskRuns = [
      {
        id: 'run-1',
        task_id: 'task-1',
        trigger_type: 'manual',
        status: 'succeeded',
        conversation_id: 'conv-run-1',
        started_at: '2026-03-11T08:30:00.000',
        finished_at: '2026-03-11T08:31:00.000',
        error_message: null,
      },
    ]

    const wrapper = mount(App, {
      shallow: true,
    })

    await wrapper.get('[data-testid="open-task-drawer-btn"]').trigger('click')
    await flushPromises()

    wrapper.findComponent({ name: 'TaskDrawer' }).vm.$emit(
      'open-conversation',
      chatStoreMock.inspectionTaskRuns[0],
    )
    await flushPromises()

    expect(chatStoreMock.streamInspectionTaskRunConversation).toHaveBeenCalledWith(
      'run-1',
      'conv-run-1',
    )
    expect(chatStoreMock.switchConversation).not.toHaveBeenCalled()
  })

  test('keeps the title row on stable layout classes for long conversation titles', () => {
    chatStoreMock.currentConversationId = 'conv-1'
    chatStoreMock.messages = [
      {
        id: 'msg-1',
        role: 'user',
        content:
          '这是一个非常非常非常非常非常非常非常长的标题，用来验证标题区域不会因为操作控件而错位',
        type: 'text',
        timestamp: 1,
      },
    ]
    chatStoreMock.conversations = [
      {
        id: 'conv-1',
        title:
          '这是一个非常非常非常非常非常非常非常长的标题，用来验证标题区域不会因为操作控件而错位',
        source: 'web',
        agent_id: 'dba',
        created_at: null,
        updated_at: null,
      },
    ]

    const wrapper = mount(App, {
      shallow: true,
    })

    expect(wrapper.get('.chat-title-row').classes()).toContain('chat-title-row-stable')
  })

  test('keeps the title action row vertically aligned on desktop', () => {
    chatStoreMock.currentConversationId = 'conv-1'
    chatStoreMock.messages = [
      {
        id: 'msg-1',
        role: 'user',
        content: '请帮我巡检 peets mysql',
        type: 'text',
        timestamp: 1,
      },
    ]
    chatStoreMock.conversations = [
      {
        id: 'conv-1',
        title: 'peets mysql 巡检',
        source: 'web',
        agent_id: 'dba',
        created_at: null,
        updated_at: null,
      },
    ]

    const wrapper = mount(App, {
      shallow: true,
    })

    expect(wrapper.get('.chat-title-row').classes()).toContain('chat-title-row-actions-inline')
  })

  test('uses the shared panel shell class for both task and inspector drawers', async () => {
    const wrapper = mount(App, {
      shallow: true,
    })

    await wrapper.get('[data-testid="open-task-drawer-btn"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('.task-drawer-shell').classes()).toContain('ui-panel-shell')

    if (!chromeHarness.showInspector) {
      throw new Error('showInspector ref was not captured')
    }

    chromeHarness.showInspector.value = true
    await nextTick()

    expect(wrapper.get('.inspector-drawer').classes()).toContain('ui-panel-shell')
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

  test('sends pending attachments together with the next user message', async () => {
    chatStoreMock.conversationAttachments = [
      {
        id: 'att-1',
        conversation_id: 'conv-1',
        original_name: 'report-a.md',
        stored_name: 'report-a.md',
        relative_path: 'data/conversation_attachments/conv-1/report-a.md',
        mime_type: 'text/markdown',
        size_bytes: 100,
        created_at: '2026-03-10T10:00:00.000',
      },
      {
        id: 'att-2',
        conversation_id: 'conv-1',
        original_name: 'report-b.md',
        stored_name: 'report-b.md',
        relative_path: 'data/conversation_attachments/conv-1/report-b.md',
        mime_type: 'text/markdown',
        size_bytes: 120,
        created_at: '2026-03-10T10:01:00.000',
      },
    ]

    mount(App, {
      shallow: true,
    })

    const sendMessage = composerHarness.sendMessage
    if (!sendMessage) {
      throw new Error('composer sendMessage was not captured')
    }

    const result = await sendMessage('帮我合并汇总信息', '帮我合并汇总信息')

    expect(result).toBe(true)
    expect(chatStoreMock.sendMessage).toHaveBeenCalledWith('帮我合并汇总信息', '帮我合并汇总信息', {
      attachments: chatStoreMock.conversationAttachments,
    })
  })

  test('keeps only unsubmitted attachments in the composer attachment bar', () => {
    chatStoreMock.messages = [
      {
        id: 'msg-1',
        role: 'user',
        content: '帮我合并汇总信息',
        type: 'text',
        timestamp: 1,
        attachments: [
          {
            id: 'att-1',
            original_name: 'report-a.md',
            stored_name: 'report-a.md',
            relative_path: 'data/conversation_attachments/conv-1/report-a.md',
            mime_type: 'text/markdown',
            size_bytes: 100,
            created_at: '2026-03-10T10:00:00.000',
          },
        ],
      },
    ]
    chatStoreMock.conversationAttachments = [
      {
        id: 'att-1',
        conversation_id: 'conv-1',
        original_name: 'report-a.md',
        stored_name: 'report-a.md',
        relative_path: 'data/conversation_attachments/conv-1/report-a.md',
        mime_type: 'text/markdown',
        size_bytes: 100,
        created_at: '2026-03-10T10:00:00.000',
      },
      {
        id: 'att-2',
        conversation_id: 'conv-1',
        original_name: 'report-b.md',
        stored_name: 'report-b.md',
        relative_path: 'data/conversation_attachments/conv-1/report-b.md',
        mime_type: 'text/markdown',
        size_bytes: 120,
        created_at: '2026-03-10T10:01:00.000',
      },
    ]

    const wrapper = mount(App, {
      shallow: true,
    })
    const attachmentBar = wrapper.findComponent({ name: 'ConversationAttachmentBar' })

    expect(attachmentBar.props('attachments')).toEqual([chatStoreMock.conversationAttachments[1]])
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

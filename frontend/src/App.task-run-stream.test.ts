import { flushPromises, mount } from '@vue/test-utils'
import { computed, ref } from 'vue'

import App from './App.vue'
import type { ConversationItem, InspectionTaskRun } from './stores/chat'

const chatStoreMock = {
  messages: [] as Array<Record<string, unknown>>,
  agents: [
    { id: 'general', label: 'General' },
    { id: 'dba', label: 'DBA' },
  ],
  activeAgentId: 'dba',
  activeAgent: { id: 'dba', label: 'DBA' },
  conversations: [] as ConversationItem[],
  inspectionTasks: [],
  taskNotifications: [],
  inspectionTaskRuns: [
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
  ] as InspectionTaskRun[],
  currentConversationId: null as string | null,
  draftAgentId: 'dba',
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
  taskNotificationToast: null,
  taskNotificationError: null as string | null,
  isTaskNotificationLoading: false,
  conversationAttachments: [],
  attachmentError: null as string | null,
  isAttachmentUploading: false,
  sendMessage: vi.fn(),
  uploadConversationAttachment: vi.fn(async () => true),
  deleteConversationAttachment: vi.fn(async () => {}),
  fetchConversationAttachments: vi.fn(async () => {}),
  resolveCloudRequestContext: vi.fn(async () => ({
    matched: false,
    ambiguous: false,
    selection_required: false,
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
  fetchInspectionTasks: vi.fn(async () => {}),
  fetchInspectionTaskRuns: vi.fn(async () => {}),
  fetchTaskNotifications: vi.fn(async () => {}),
  buildInspectionTaskDraft: vi.fn(async () => null),
  createInspectionTaskFromConversationMessage: vi.fn(async () => ({ status: 'not_task_creation' })),
  createInspectionTaskFromConversationMessageStream: vi.fn(async () => ({ status: 'not_task_creation' })),
  createInspectionTask: vi.fn(async () => null),
  updateInspectionTask: vi.fn(async () => null),
  deleteInspectionTask: vi.fn(async () => false),
  triggerInspectionTask: vi.fn(async () => null),
  fetchSkills: vi.fn(async () => {}),
  fetchMcpServers: vi.fn(async () => {}),
  fetchMemoryTree: vi.fn(async () => {}),
  openMemoryDocument: vi.fn(async () => {}),
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
  useChatComposer: () => ({
    inputText: ref(''),
    composerInput: ref<HTMLTextAreaElement | null>(null),
    showMentions: ref(false),
    mentionIndex: ref(0),
    filteredSkills: computed(() => []),
    inputPlaceholder: computed(() => 'Send a message'),
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
    heroTitle: computed(() => 'Work with me'),
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

describe('App task run streaming open', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
  })

  test('opens a task run via streamed conversation playback', async () => {
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
})

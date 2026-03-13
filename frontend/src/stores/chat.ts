import { defineStore } from 'pinia'
import { computed, reactive, ref, watch } from 'vue'
import { createAttachmentDomain } from './chat/attachments'
import { createAuthDomain } from './chat/auth'
import { createConversationDomain } from './chat/conversations'
import {
  CHAT_ENTRY_AGENT_ID,
  apiFetch,
  getDefaultAgentId,
  resolveAgentId,
} from './chat/helpers'
import { createMcpDomain } from './chat/mcp'
import { createMemoryDomain } from './chat/memory'
import { createTaskNotificationDomain } from './chat/notifications'
import { createSocketDomain } from './chat/socket'
import { createTaskDomain } from './chat/tasks'
import { isMysqlInspectionIntent } from '../utils/mysqlInspection'
import type {
  AgentInfo,
  AuthUser,
  ChatMessage,
  CloudContextResolution,
  ConversationAttachment,
  ConversationItem,
  InspectionTask,
  InspectionTaskRun,
  McpServer,
  MemoryDocument,
  MemoryNode,
  Skill,
  TaskNotification,
} from './chat/types'

export * from './chat/types'

export const useChatStore = defineStore('chat', () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const defaultWsUrl = `${protocol}//${window.location.host}/ws/chat`
  const wsUrl = import.meta.env.VITE_WS_URL || defaultWsUrl
  const backendUrl = import.meta.env.VITE_API_BASE_URL || ''

  const messages = reactive<ChatMessage[]>([])
  const isConnected = ref(false)
  const isLoading = ref(false)
  const agents = ref<AgentInfo[]>([])
  const skills = ref<Skill[]>([])
  const mcpServers = ref<McpServer[]>([])
  const mcpConfigText = ref('')
  const conversations = ref<ConversationItem[]>([])
  const conversationAttachments = ref<ConversationAttachment[]>([])
  const inspectionTasks = ref<InspectionTask[]>([])
  const inspectionTaskRuns = ref<InspectionTaskRun[]>([])
  const taskNotifications = ref<TaskNotification[]>([])
  const currentConversationId = ref<string | null>(null)
  const draftAgentId = ref(CHAT_ENTRY_AGENT_ID)
  const memoryTree = ref<MemoryNode[]>([])
  const selectedMemoryPath = ref<string | null>(null)
  const memoryContent = ref<MemoryDocument | null>(null)
  const memoryError = ref<string | null>(null)
  const attachmentError = ref<string | null>(null)
  const isMemoryTreeLoading = ref(false)
  const isMemoryContentLoading = ref(false)
  const isMemoryDeleting = ref(false)
  const isMemoryTreeLoaded = ref(false)
  const isAttachmentUploading = ref(false)
  const isMcpLoading = ref(false)
  const mcpError = ref<string | null>(null)
  const inspectionTaskError = ref<string | null>(null)
  const testingServerIds = ref<string[]>([])
  const deletingAttachmentIds = ref<string[]>([])
  const isInspectionTaskLoading = ref(false)
  const unreadTaskNotificationCount = ref(0)
  const taskNotificationToast = ref<TaskNotification | null>(null)
  const taskNotificationError = ref<string | null>(null)
  const isTaskNotificationLoading = ref(false)
  const authEnabled = ref(false)
  const isAuthenticated = ref(false)
  const authUser = ref<AuthUser | null>(null)
  const authPermissions = ref<string[]>([])
  const availablePermissions = ref<string[]>([])
  const loginUrl = ref('/api/auth/login')
  const logoutUrl = ref('/api/auth/logout')
  const oidcLoginEnabled = ref(false)
  const passwordLoginEnabled = ref(false)
  const loginMethods = ref<string[]>([])
  const authError = ref<string | null>(null)
  const isAuthLoading = ref(false)

  const isMemoryLoading = computed(
    () =>
      isMemoryTreeLoading.value ||
      isMemoryContentLoading.value ||
      isMemoryDeleting.value,
  )

  const currentConversation = computed(
    () =>
      conversations.value.find(
        (conversation) => conversation.id === currentConversationId.value,
      ) ?? null,
  )

  const activeAgentId = computed(
    () =>
      resolveAgentId(
        currentConversation.value?.agent_id || draftAgentId.value || CHAT_ENTRY_AGENT_ID,
        agents.value,
      ),
  )

  const activeAgent = computed(
    () => agents.value.find((agent) => agent.id === activeAgentId.value) ?? null,
  )

  const wsState = {
    current: null as WebSocket | null,
  }

  let messageIdCounter = 0

  function genId(): string {
    return `msg-${Date.now()}-${messageIdCounter++}`
  }

  const memoryDomain = createMemoryDomain({
    backendUrl,
    memoryTree,
    selectedMemoryPath,
    memoryContent,
    memoryError,
    isMemoryTreeLoading,
    isMemoryContentLoading,
    isMemoryDeleting,
    isMemoryTreeLoaded,
  })

  const mcpDomain = createMcpDomain({
    backendUrl,
    mcpServers,
    mcpConfigText,
    isMcpLoading,
    mcpError,
    testingServerIds,
  })
  const authDomain = createAuthDomain({
    backendUrl,
    authEnabled,
    isAuthenticated,
    authUser,
    authPermissions,
    availablePermissions,
    loginUrl,
    logoutUrl,
    oidcLoginEnabled,
    passwordLoginEnabled,
    loginMethods,
    authError,
    isAuthLoading,
  })

  async function fetchAgents() {
    try {
      const res = await apiFetch(`${backendUrl}/api/agents`)
      agents.value = await res.json()
      draftAgentId.value = resolveAgentId(
        draftAgentId.value || getDefaultAgentId(agents.value),
        agents.value,
      )
    } catch (error) {
      console.warn('获取 Agents 列表失败:', error)
    }
  }

  async function fetchSkills(agentId?: string) {
    try {
      const targetAgentId = resolveAgentId(agentId || activeAgentId.value, agents.value)
      const res = await apiFetch(
        `${backendUrl}/api/skills?agent_id=${encodeURIComponent(targetAgentId)}`,
      )
      skills.value = await res.json()
    } catch (error) {
      console.warn('获取 Skills 列表失败:', error)
    }
  }

  async function resolveCloudRequestContext(
    message: string,
    credentialRef?: string,
  ): Promise<CloudContextResolution> {
    const res = await apiFetch(`${backendUrl}/api/cloud-credentials/resolve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        agent_id: isMysqlInspectionIntent(message) ? 'dba' : CHAT_ENTRY_AGENT_ID,
        credential_ref: credentialRef ?? null,
      }),
    })

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`)
    }

    return (await res.json()) as CloudContextResolution
  }

  function setDraftAgent(agentId: string) {
    void agentId
    draftAgentId.value = resolveAgentId(CHAT_ENTRY_AGENT_ID, agents.value)
    void fetchSkills(draftAgentId.value)

    if (!currentConversationId.value && wsState.current?.readyState === WebSocket.OPEN) {
      wsState.current.send(
        JSON.stringify({
          type: 'init',
          conversation_id: null,
          agent_id: CHAT_ENTRY_AGENT_ID,
        }),
      )
    }
  }

  const conversationDomain = createConversationDomain({
    backendUrl,
    messages,
    conversations,
    currentConversationId,
    draftAgentId,
    activeAgentId,
    agents,
    isLoading,
    wsState,
    fetchSkills,
  })

  const attachmentDomain = createAttachmentDomain({
    backendUrl,
    conversationAttachments,
    attachmentError,
    isAttachmentUploading,
    deletingAttachmentIds,
    currentConversationId,
    draftAgentId,
    activeAgentId,
    conversations,
    agents,
    wsState,
    fetchConversations: conversationDomain.fetchConversations,
    fetchSkills,
  })

  const taskDomain = createTaskDomain({
    backendUrl,
    inspectionTasks,
    inspectionTaskRuns,
    inspectionTaskError,
    isInspectionTaskLoading,
  })

  const taskNotificationDomain = createTaskNotificationDomain({
    backendUrl,
    taskNotifications,
    unreadTaskNotificationCount,
    taskNotificationToast,
    taskNotificationError,
    isTaskNotificationLoading,
  })

  watch(
    currentConversationId,
    (conversationId) => {
      if (!conversationId) {
        attachmentDomain.clearConversationAttachments()
        return
      }

      void attachmentDomain.fetchConversationAttachments(conversationId)
    },
    { immediate: true },
  )

  const socketDomain = createSocketDomain({
    wsUrl,
    messages,
    conversations,
    currentConversationId,
    draftAgentId,
    activeAgentId,
    agents,
    isConnected,
    isLoading,
    wsState,
    genId,
    fetchConversations: conversationDomain.fetchConversations,
    handleMemoryArtifact: memoryDomain.handleMemoryArtifact,
    handleTaskNotificationEvent: taskNotificationDomain.handleTaskNotificationEvent,
  })

  return {
    messages,
    isConnected,
    isLoading,
    agents,
    skills,
    mcpServers,
    mcpConfigText,
    conversations,
    conversationAttachments,
    inspectionTasks,
    inspectionTaskRuns,
    taskNotifications,
    currentConversationId,
    draftAgentId,
    activeAgentId,
    activeAgent,
    memoryTree,
    selectedMemoryPath,
    memoryContent,
    memoryError,
    attachmentError,
    isMemoryLoading,
    isAttachmentUploading,
    isMcpLoading,
    mcpError,
    inspectionTaskError,
    unreadTaskNotificationCount,
    taskNotificationToast,
    taskNotificationError,
    testingServerIds,
    deletingAttachmentIds,
    isInspectionTaskLoading,
    isTaskNotificationLoading,
    authEnabled,
    isAuthenticated,
    authUser,
    authPermissions,
    availablePermissions,
    loginUrl,
    logoutUrl,
    oidcLoginEnabled,
    passwordLoginEnabled,
    loginMethods,
    authError,
    isAuthLoading,
    connect: socketDomain.connect,
    sendMessage: socketDomain.sendMessage,
    clearChat: socketDomain.clearChat,
    abortAgent: socketDomain.abortAgent,
    fetchAgents,
    fetchAuthStatus: authDomain.fetchAuthStatus,
    hasPermission: authDomain.hasPermission,
    login: authDomain.login,
    loginWithPassword: authDomain.loginWithPassword,
    logout: authDomain.logout,
    fetchConversations: conversationDomain.fetchConversations,
    setDraftAgent,
    createConversation: conversationDomain.createConversation,
    switchConversation: conversationDomain.switchConversation,
    streamInspectionTaskRunConversation:
      conversationDomain.streamInspectionTaskRunConversation,
    deleteConversation: conversationDomain.deleteConversation,
    updateConversationTitle: conversationDomain.updateConversationTitle,
    fetchConversationAttachments: attachmentDomain.fetchConversationAttachments,
    uploadConversationAttachment: attachmentDomain.uploadConversationAttachment,
    deleteConversationAttachment: attachmentDomain.deleteConversationAttachment,
    fetchInspectionTasks: taskDomain.fetchInspectionTasks,
    fetchInspectionTaskRuns: taskDomain.fetchInspectionTaskRuns,
    buildInspectionTaskDraft: taskDomain.buildInspectionTaskDraft,
    createInspectionTaskFromConversationMessage:
      taskDomain.createInspectionTaskFromConversationMessage,
    createInspectionTaskFromConversationMessageStream:
      taskDomain.createInspectionTaskFromConversationMessageStream,
    createInspectionTask: taskDomain.createInspectionTask,
    updateInspectionTask: taskDomain.updateInspectionTask,
    deleteInspectionTask: taskDomain.deleteInspectionTask,
    triggerInspectionTask: taskDomain.triggerInspectionTask,
    fetchTaskNotifications: taskNotificationDomain.fetchTaskNotifications,
    markTaskNotificationRead: taskNotificationDomain.markTaskNotificationRead,
    markAllTaskNotificationsRead: taskNotificationDomain.markAllTaskNotificationsRead,
    dismissTaskNotificationToast: taskNotificationDomain.dismissTaskNotificationToast,
    downloadTaskNotificationReport: taskNotificationDomain.downloadTaskNotificationReport,
    fetchSkills,
    resolveCloudRequestContext,
    fetchMcpConfig: mcpDomain.fetchMcpConfig,
    fetchMcpServers: mcpDomain.fetchMcpServers,
    saveMcpConfig: mcpDomain.saveMcpConfig,
    testMcpServer: mcpDomain.testMcpServer,
    fetchMemoryTree: memoryDomain.fetchMemoryTree,
    fetchMemoryContent: memoryDomain.fetchMemoryContent,
    deleteMemoryFile: memoryDomain.deleteMemoryFile,
    openMemoryDocument: memoryDomain.openMemoryDocument,
  }
})

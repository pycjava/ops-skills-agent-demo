import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import { createConversationDomain } from './chat/conversations'
import { getDefaultAgentId, resolveAgentId } from './chat/helpers'
import { createMcpDomain } from './chat/mcp'
import { createMemoryDomain } from './chat/memory'
import { createSocketDomain } from './chat/socket'
import type {
  AgentInfo,
  ChatMessage,
  ConversationItem,
  McpServer,
  MemoryDocument,
  MemoryNode,
  Skill,
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
  const conversations = ref<ConversationItem[]>([])
  const currentConversationId = ref<string | null>(null)
  const draftAgentId = ref('general')
  const memoryTree = ref<MemoryNode[]>([])
  const selectedMemoryPath = ref<string | null>(null)
  const memoryContent = ref<MemoryDocument | null>(null)
  const memoryError = ref<string | null>(null)
  const isMemoryTreeLoading = ref(false)
  const isMemoryContentLoading = ref(false)
  const isMemoryDeleting = ref(false)
  const isMemoryTreeLoaded = ref(false)
  const isMcpLoading = ref(false)
  const mcpError = ref<string | null>(null)
  const testingServerIds = ref<string[]>([])

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
    () => currentConversation.value?.agent_id || draftAgentId.value || 'general',
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
    isMcpLoading,
    mcpError,
    testingServerIds,
  })

  async function fetchAgents() {
    try {
      const res = await fetch(`${backendUrl}/api/agents`)
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
      const res = await fetch(
        `${backendUrl}/api/skills?agent_id=${encodeURIComponent(targetAgentId)}`,
      )
      skills.value = await res.json()
    } catch (error) {
      console.warn('获取 Skills 列表失败:', error)
    }
  }

  function setDraftAgent(agentId: string) {
    draftAgentId.value = resolveAgentId(agentId, agents.value)
    void fetchSkills(draftAgentId.value)

    if (!currentConversationId.value && wsState.current?.readyState === WebSocket.OPEN) {
      wsState.current.send(
        JSON.stringify({
          type: 'init',
          conversation_id: null,
          agent_id: draftAgentId.value,
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
  })

  return {
    messages,
    isConnected,
    isLoading,
    agents,
    skills,
    mcpServers,
    conversations,
    currentConversationId,
    draftAgentId,
    activeAgentId,
    activeAgent,
    memoryTree,
    selectedMemoryPath,
    memoryContent,
    memoryError,
    isMemoryLoading,
    isMcpLoading,
    mcpError,
    testingServerIds,
    connect: socketDomain.connect,
    sendMessage: socketDomain.sendMessage,
    clearChat: socketDomain.clearChat,
    abortAgent: socketDomain.abortAgent,
    fetchAgents,
    fetchConversations: conversationDomain.fetchConversations,
    setDraftAgent,
    createConversation: conversationDomain.createConversation,
    switchConversation: conversationDomain.switchConversation,
    deleteConversation: conversationDomain.deleteConversation,
    updateConversationTitle: conversationDomain.updateConversationTitle,
    fetchSkills,
    fetchMcpServers: mcpDomain.fetchMcpServers,
    createMcpServer: mcpDomain.createMcpServer,
    updateMcpServer: mcpDomain.updateMcpServer,
    deleteMcpServer: mcpDomain.deleteMcpServer,
    testMcpServer: mcpDomain.testMcpServer,
    fetchMemoryTree: memoryDomain.fetchMemoryTree,
    fetchMemoryContent: memoryDomain.fetchMemoryContent,
    deleteMemoryFile: memoryDomain.deleteMemoryFile,
    openMemoryDocument: memoryDomain.openMemoryDocument,
  }
})

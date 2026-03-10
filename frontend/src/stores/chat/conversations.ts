import type { ComputedRef, Ref } from 'vue'
import { getConversationTitleError, normalizeConversationTitle } from '../../utils/conversationTitle'
import {
  findRecentToolInput,
  normalizeAttachmentSnapshots,
  readErrorMessage,
  resolveConversationAgentId,
  stripSystemHint,
} from './helpers'
import type {
  AgentInfo,
  ChatMessage,
  ConversationHistoryMessage,
  ConversationItem,
} from './types'

interface ConversationDomainDeps {
  backendUrl: string
  messages: ChatMessage[]
  conversations: Ref<ConversationItem[]>
  currentConversationId: Ref<string | null>
  draftAgentId: Ref<string>
  activeAgentId: ComputedRef<string>
  agents: Ref<AgentInfo[]>
  isLoading: Ref<boolean>
  wsState: { current: WebSocket | null }
  fetchSkills: (agentId?: string) => Promise<void>
}

function sendConversationInit(
  wsState: { current: WebSocket | null },
  conversationId: string | null,
  agentId: string,
) {
  if (!wsState.current || wsState.current.readyState !== WebSocket.OPEN) return

  wsState.current.send(
    JSON.stringify({
      type: 'init',
      conversation_id: conversationId,
      agent_id: agentId,
    }),
  )
}

export function createConversationDomain({
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
}: ConversationDomainDeps) {
  async function fetchConversations(query?: string) {
    try {
      const url = query?.trim()
        ? `${backendUrl}/api/conversations?q=${encodeURIComponent(query.trim())}`
        : `${backendUrl}/api/conversations`
      const res = await fetch(url)
      conversations.value = await res.json()
    } catch (error) {
      console.warn('获取会话列表失败:', error)
    }
  }

  function createConversation() {
    draftAgentId.value = activeAgentId.value
    currentConversationId.value = null
    messages.length = 0
    isLoading.value = false
    void fetchSkills(draftAgentId.value)
    sendConversationInit(wsState, null, draftAgentId.value)
  }

  async function switchConversation(convId: string) {
    currentConversationId.value = convId
    messages.length = 0
    isLoading.value = false

    const nextAgentId = resolveConversationAgentId(
      convId,
      conversations.value,
      draftAgentId.value,
      agents.value,
    )
    draftAgentId.value = nextAgentId

    try {
      const res = await fetch(`${backendUrl}/api/conversations/${convId}/messages`)
      const historyMessages: ConversationHistoryMessage[] = await res.json()

      for (const message of historyMessages) {
        messages.push({
          id: message.id,
          role: message.role as 'user' | 'assistant' | 'system',
          content: message.role === 'user' ? stripSystemHint(message.content) : message.content,
          type: message.type as 'text' | 'tool_call' | 'tool_result' | 'error',
          agentId: message.agent_id || undefined,
          toolName: message.tool_name || undefined,
          toolInput:
            message.tool_input ||
            (message.type === 'tool_result' && message.tool_name
              ? findRecentToolInput(messages, message.tool_name)
              : undefined),
          attachments: normalizeAttachmentSnapshots(message.attachments_snapshot),
          thinking: message.thinking || undefined,
          timestamp: message.created_at ? new Date(message.created_at).getTime() : Date.now(),
        })
      }
    } catch (error) {
      console.warn('加载历史消息失败:', error)
    }

    await fetchSkills(nextAgentId)
    sendConversationInit(wsState, convId, nextAgentId)
  }

  async function deleteConversation(convId: string) {
    try {
      await fetch(`${backendUrl}/api/conversations/${convId}`, {
        method: 'DELETE',
      })
      conversations.value = conversations.value.filter((conversation) => conversation.id !== convId)

      if (currentConversationId.value === convId) {
        if (conversations.value.length > 0 && conversations.value[0]) {
          await switchConversation(conversations.value[0].id)
        } else {
          currentConversationId.value = null
          messages.length = 0
          isLoading.value = false
          await fetchSkills(draftAgentId.value)
          sendConversationInit(wsState, null, draftAgentId.value)
        }
      }
    } catch (error) {
      console.warn('删除会话失败:', error)
    }
  }

  async function updateConversationTitle(convId: string, title: string): Promise<ConversationItem> {
    const validationError = getConversationTitleError(title)
    if (validationError) {
      throw new Error(validationError)
    }

    const normalizedTitle = normalizeConversationTitle(title)
    const res = await fetch(`${backendUrl}/api/conversations/${encodeURIComponent(convId)}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ title: normalizedTitle }),
    })

    if (!res.ok) {
      throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
    }

    const updatedConversation: ConversationItem = await res.json()
    let found = false

    conversations.value = conversations.value.map((conversation) => {
      if (conversation.id !== updatedConversation.id) {
        return conversation
      }

      found = true
      return updatedConversation
    })

    if (!found) {
      conversations.value = [updatedConversation, ...conversations.value]
    }

    return updatedConversation
  }

  return {
    fetchConversations,
    createConversation,
    switchConversation,
    deleteConversation,
    updateConversationTitle,
  }
}

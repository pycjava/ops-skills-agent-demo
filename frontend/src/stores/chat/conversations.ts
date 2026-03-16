import type { ComputedRef, Ref } from 'vue'
import { getConversationTitleError, normalizeConversationTitle } from '../../utils/conversationTitle'
import {
  apiFetch,
  CHAT_ENTRY_AGENT_ID,
  findRecentToolInput,
  normalizeAgentId,
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
  InspectionTaskRunConversationStreamEvent,
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

function pushConversationHistoryMessage(
  messages: ChatMessage[],
  message: ConversationHistoryMessage,
) {
  messages.push({
    id: message.id,
    role: message.role as 'user' | 'assistant' | 'system',
    content: message.role === 'user' ? stripSystemHint(message.content) : message.content,
    type: message.type as 'text' | 'tool_call' | 'tool_result' | 'error',
    agentId: normalizeAgentId(message.agent_id),
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
      const res = await apiFetch(url)
      const payload: ConversationItem[] = await res.json()
      conversations.value = payload.map((conversation) => ({
        ...conversation,
        agent_id: normalizeAgentId(conversation.agent_id) || conversation.agent_id,
      }))
    } catch (error) {
      console.warn('获取会话列表失败:', error)
    }
  }

  function createConversation() {
    void activeAgentId
    draftAgentId.value = CHAT_ENTRY_AGENT_ID
    currentConversationId.value = null
    messages.length = 0
    isLoading.value = false
    void fetchSkills(CHAT_ENTRY_AGENT_ID)
    sendConversationInit(wsState, null, CHAT_ENTRY_AGENT_ID)
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
      const res = await apiFetch(`${backendUrl}/api/conversations/${convId}/messages`)
      const historyMessages: ConversationHistoryMessage[] = await res.json()

      for (const message of historyMessages) {
        pushConversationHistoryMessage(messages, message)
      }
    } catch (error) {
      console.warn('加载历史消息失败:', error)
    }

    await fetchSkills(nextAgentId)
    sendConversationInit(wsState, convId, nextAgentId)
  }

  async function streamInspectionTaskRunConversation(runId: string, convId: string) {
    isLoading.value = true

    let res: Response
    try {
      res = await apiFetch(
        `${backendUrl}/api/inspection-tasks/runs/${encodeURIComponent(runId)}/conversation/stream`,
      )
    } catch (error) {
      isLoading.value = false
      console.warn('打开任务执行会话失败:', error)
      return
    }

    if (!res.ok || !res.body) {
      isLoading.value = false
      console.warn(
        '打开任务执行会话失败:',
        await readErrorMessage(res, `HTTP ${res.status}`),
      )
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let nextAgentId = resolveConversationAgentId(
      convId,
      conversations.value,
      draftAgentId.value,
      agents.value,
    )

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const jsonStr = line.slice(6).trim()
        if (!jsonStr) continue

        let event: InspectionTaskRunConversationStreamEvent
        try {
          event = JSON.parse(jsonStr) as InspectionTaskRunConversationStreamEvent
        } catch {
          continue
        }

        if (event.type === 'history_start') {
          currentConversationId.value = event.conversation_id
          messages.length = 0
          nextAgentId = normalizeAgentId(event.agent_id) || nextAgentId
          draftAgentId.value = nextAgentId
          await fetchSkills(nextAgentId)
          sendConversationInit(wsState, event.conversation_id, nextAgentId)

          const nextConversation: ConversationItem = {
            id: event.conversation_id,
            title: event.title,
            source: 'task',
            agent_id: nextAgentId,
            created_at: null,
            updated_at: null,
          }
          const existingIndex = conversations.value.findIndex(
            (conversation) => conversation.id === event.conversation_id,
          )
          if (existingIndex === -1) {
            conversations.value = [nextConversation, ...conversations.value]
          } else {
            conversations.value = conversations.value.map((conversation, index) =>
              index === existingIndex ? { ...conversation, ...nextConversation } : conversation,
            )
          }
          continue
        }

        if (event.type === 'message') {
          pushConversationHistoryMessage(messages, event.message)
          continue
        }

        if (event.type === 'run_status') {
          if (event.status === 'failed' && event.error_message) {
            messages.push({
              id: `run-status-${event.run_id}`,
              role: 'system',
              content: event.error_message,
              type: 'error',
              agentId: nextAgentId,
              timestamp: event.finished_at ? new Date(event.finished_at).getTime() : Date.now(),
            })
          }
          continue
        }

        if (event.type === 'error') {
          messages.push({
            id: `run-error-${Date.now()}`,
            role: 'system',
            content: event.content,
            type: 'error',
            agentId: nextAgentId,
            timestamp: Date.now(),
          })
          isLoading.value = false
          continue
        }

        if (event.type === 'done') {
          isLoading.value = false
        }
      }
    }

    isLoading.value = false
    await fetchConversations()
  }

  async function deleteConversation(convId: string) {
    try {
      await apiFetch(`${backendUrl}/api/conversations/${convId}`, {
        method: 'DELETE',
      })
      conversations.value = conversations.value.filter((conversation) => conversation.id !== convId)

      if (currentConversationId.value === convId) {
        if (conversations.value.length > 0 && conversations.value[0]) {
          await switchConversation(conversations.value[0].id)
        } else {
          currentConversationId.value = null
          draftAgentId.value = CHAT_ENTRY_AGENT_ID
          messages.length = 0
          isLoading.value = false
          await fetchSkills(CHAT_ENTRY_AGENT_ID)
          sendConversationInit(wsState, null, CHAT_ENTRY_AGENT_ID)
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
    const res = await apiFetch(`${backendUrl}/api/conversations/${encodeURIComponent(convId)}`, {
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
    streamInspectionTaskRunConversation,
    deleteConversation,
    updateConversationTitle,
  }
}

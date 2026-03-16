import type { ComputedRef, Ref } from 'vue'
import {
  CHAT_ENTRY_AGENT_ID,
  findRecentToolInput,
  normalizeAgentId,
  resolveConversationAgentId,
  toAttachmentSnapshot,
} from './helpers'
import { normalizeArtifactKind } from './memory'
import type {
  AgentInfo,
  ChatMessage,
  ConversationItem,
  SendMessageOptions,
  TaskNotification,
} from './types'

interface SocketDomainDeps {
  wsUrl: string
  messages: ChatMessage[]
  conversations: Ref<ConversationItem[]>
  currentConversationId: Ref<string | null>
  draftAgentId: Ref<string>
  activeAgentId: ComputedRef<string>
  agents: Ref<AgentInfo[]>
  isConnected: Ref<boolean>
  isLoading: Ref<boolean>
  wsState: { current: WebSocket | null }
  genId: () => string
  fetchConversations: () => Promise<void>
  handleMemoryArtifact: (toolInput?: Record<string, unknown>) => void
  handleTaskNotificationEvent: (
    notification: TaskNotification,
    unreadCount?: number,
  ) => void
}

function finishStreamingAssistantMessage(messages: ChatMessage[]) {
  if (messages.length === 0) return

  const lastMessage = messages[messages.length - 1]
  if (lastMessage && lastMessage.role === 'assistant' && lastMessage.streaming) {
    lastMessage.streaming = false
  }
}

export function createSocketDomain({
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
  fetchConversations,
  handleMemoryArtifact,
  handleTaskNotificationEvent,
}: SocketDomainDeps) {
  void activeAgentId
  const pendingRoutedAgentIds: string[] = []
  let pendingAssistantAgentId: string | undefined

  function connect() {
    if (
      wsState.current &&
      (wsState.current.readyState === WebSocket.OPEN ||
        wsState.current.readyState === WebSocket.CONNECTING)
    ) {
      return
    }

    wsState.current = new WebSocket(wsUrl)

    wsState.current.onopen = () => {
      isConnected.value = true
      wsState.current?.send(
        JSON.stringify({
          type: 'init',
          conversation_id: currentConversationId.value,
          agent_id: currentConversationId.value ? undefined : CHAT_ENTRY_AGENT_ID,
        }),
      )
    }

    wsState.current.onmessage = (event) => {
      const data = JSON.parse(event.data)

      switch (data.type) {
        case 'session':
          currentConversationId.value = data.conversation_id || null
          if (normalizeAgentId(data.agent_id)) {
            draftAgentId.value = normalizeAgentId(data.agent_id) || CHAT_ENTRY_AGENT_ID
          }
          break

        case 'text':
          messages.push({
            id: genId(),
            role: 'assistant',
            content: data.content,
            type: 'text',
            agentId:
              pendingAssistantAgentId ||
              normalizeAgentId(data.agent_id) ||
              CHAT_ENTRY_AGENT_ID,
            timestamp: Date.now(),
          })
          break

        case 'text_delta': {
          const incomingAgentId =
            pendingAssistantAgentId ||
            normalizeAgentId(data.agent_id) ||
            CHAT_ENTRY_AGENT_ID
          const lastMessage = messages[messages.length - 1]
          if (
            lastMessage &&
            lastMessage.role === 'assistant' &&
            lastMessage.type === 'text' &&
            lastMessage.agentId === incomingAgentId &&
            lastMessage.streaming
          ) {
            lastMessage.content += data.content
            break
          }

          messages.push({
            id: genId(),
            role: 'assistant',
            content: data.content,
            type: 'text',
            agentId: incomingAgentId,
            timestamp: Date.now(),
            streaming: true,
          })
          break
        }

        case 'thinking_delta': {
          const incomingAgentId =
            pendingAssistantAgentId ||
            normalizeAgentId(data.agent_id) ||
            CHAT_ENTRY_AGENT_ID
          const lastMessage = messages[messages.length - 1]
          if (
            lastMessage &&
            lastMessage.role === 'assistant' &&
            lastMessage.type === 'text' &&
            lastMessage.agentId === incomingAgentId &&
            lastMessage.streaming
          ) {
            lastMessage.thinking = (lastMessage.thinking || '') + data.content
            break
          }

          messages.push({
            id: genId(),
            role: 'assistant',
            content: '',
            type: 'text',
            agentId: incomingAgentId,
            timestamp: Date.now(),
            streaming: true,
            thinking: data.content,
          })
          break
        }

        case 'tool_call': {
          const toolInput =
            data.tool_input && typeof data.tool_input === 'object'
              ? (data.tool_input as Record<string, unknown>)
              : undefined
          const subagentType = normalizeAgentId(toolInput?.subagent_type)
          const sourceAgentId = normalizeAgentId(data.agent_id) || CHAT_ENTRY_AGENT_ID
          messages.push({
            id: genId(),
            role: 'system',
            content: data.tool_desc || `正在执行 Tool: **${data.tool_name}**`,
            type: 'tool_call',
            agentId: sourceAgentId,
            toolName: data.tool_name,
            toolDesc: data.tool_desc,
            toolInput:
              data.tool_name === 'task'
                ? {
                    ...(toolInput || {}),
                    ...(subagentType ? { subagent_type: subagentType } : {}),
                    source_agent_id: sourceAgentId,
                  }
                : toolInput,
            timestamp: Date.now(),
          })
          break
        }

        case 'routing': {
          const subagentType = normalizeAgentId(data.subagent_type)
          const subagentLabel = data.subagent_label || data.subagent_type
          const sourceAgentId = normalizeAgentId(data.source_agent_id || data.agent_id) || CHAT_ENTRY_AGENT_ID
          const sourceAgentLabel = data.source_agent_label || sourceAgentId
          if (subagentType) {
            pendingRoutedAgentIds.push(subagentType)
          }
          messages.push({
            id: genId(),
            role: 'system',
            content: `🔄 ${sourceAgentLabel} 正在调用 ${subagentLabel}...`,
            type: 'tool_call',
            agentId: sourceAgentId,
            toolName: 'task',
            toolDesc: `${sourceAgentLabel} 路由到 ${subagentLabel}`,
            toolInput:
              subagentType
                ? { subagent_type: subagentType, source_agent_id: sourceAgentId }
                : { source_agent_id: sourceAgentId },
            timestamp: Date.now(),
          })
          break
        }

        case 'tool_result': {
          const routedAgentId =
            data.tool_name === 'task' ? pendingRoutedAgentIds.shift() : undefined
          if (routedAgentId) {
            pendingAssistantAgentId = routedAgentId
          }
          const toolResultInput = data.tool_input || findRecentToolInput(messages, data.tool_name)
          messages.push({
            id: genId(),
            role: 'system',
            content: data.result,
            type: 'tool_result',
            agentId:
              routedAgentId ||
              normalizeAgentId(data.agent_id) ||
              pendingAssistantAgentId ||
              CHAT_ENTRY_AGENT_ID,
            toolName: data.tool_name,
            toolInput: toolResultInput,
            artifactKind: normalizeArtifactKind(data.artifact_kind),
            timestamp: Date.now(),
          })
          handleMemoryArtifact(toolResultInput)
          break
        }

        case 'done':
          isLoading.value = false
          finishStreamingAssistantMessage(messages)
          pendingAssistantAgentId = undefined
          pendingRoutedAgentIds.length = 0
          void fetchConversations()
          break

        case 'error':
          messages.push({
            id: genId(),
            role: 'system',
            content: data.content,
            type: 'error',
            agentId: normalizeAgentId(data.agent_id) || CHAT_ENTRY_AGENT_ID,
            timestamp: Date.now(),
          })
          isLoading.value = false
          pendingAssistantAgentId = undefined
          pendingRoutedAgentIds.length = 0
          break

        case 'cleared':
          messages.length = 0
          break

        case 'title_update':
          conversations.value = conversations.value.map((conversation) =>
            conversation.id === data.conversation_id
              ? { ...conversation, title: data.title }
              : conversation,
          )
          break

        case 'task_notification':
          if (data.notification) {
            handleTaskNotificationEvent(
              data.notification as TaskNotification,
              typeof data.unread_count === 'number' ? data.unread_count : undefined,
            )
          }
          break

        case 'ocr_status':
          messages.push({
            id: genId(),
            role: 'system',
            content: data.content,
            type: 'text',
            agentId: normalizeAgentId(data.agent_id) || 'ocr',
            timestamp: Date.now(),
          })
          break

        case 'ocr_result':
          messages.push({
            id: genId(),
            role: 'system',
            content: data.content,
            type: 'text',
            agentId: normalizeAgentId(data.agent_id) || 'ocr',
            timestamp: Date.now(),
          })
          break
      }
    }

    wsState.current.onclose = () => {
      const wasLoading = isLoading.value
      isConnected.value = false
      wsState.current = null

      if (wasLoading) {
        isLoading.value = false
        finishStreamingAssistantMessage(messages)
        pendingAssistantAgentId = undefined
        pendingRoutedAgentIds.length = 0
        messages.push({
          id: genId(),
          role: 'system',
          content:
            '连接已断开，本次生成已中止。若刚刚生成了临时脚本或文件，通常是后端热重载导致的，请重试一次。',
          type: 'error',
          agentId: resolveConversationAgentId(
            currentConversationId.value,
            conversations.value,
            draftAgentId.value,
            agents.value,
          ),
          timestamp: Date.now(),
        })
      }

      setTimeout(connect, 3000)
    }

    wsState.current.onerror = () => {
      isConnected.value = false
    }
  }

  function sendMessage(
    displayContent: string,
    sendContent?: string,
    options?: SendMessageOptions,
  ) {
    const normalizedContent = displayContent.trim()
    if (!normalizedContent || !wsState.current || wsState.current.readyState !== WebSocket.OPEN) {
      return
    }
    const attachments = options?.attachments?.map((attachment) =>
      toAttachmentSnapshot(attachment),
    )
    const attachmentIds = attachments?.map((attachment) => attachment.id) ?? []

    const nextAgentId = resolveConversationAgentId(
      currentConversationId.value,
      conversations.value,
      currentConversationId.value ? draftAgentId.value : CHAT_ENTRY_AGENT_ID,
      agents.value,
    )

    messages.push({
      id: genId(),
      role: 'user',
      content: normalizedContent,
      type: 'text',
      agentId: nextAgentId,
      attachments: attachments && attachments.length > 0 ? attachments : undefined,
      timestamp: Date.now(),
    })

    isLoading.value = true
    wsState.current.send(
      JSON.stringify({
        type: 'message',
        content: sendContent || normalizedContent,
        agent_id: currentConversationId.value ? undefined : CHAT_ENTRY_AGENT_ID,
        attachment_ids: attachmentIds,
      }),
    )
  }

  function clearChat() {
    if (!wsState.current || wsState.current.readyState !== WebSocket.OPEN) return
    wsState.current.send(JSON.stringify({ type: 'clear' }))
  }

  function abortAgent() {
    if (
      !wsState.current ||
      wsState.current.readyState !== WebSocket.OPEN ||
      !isLoading.value
    ) {
      return
    }
    wsState.current.send(JSON.stringify({ type: 'abort' }))
  }

  return {
    connect,
    sendMessage,
    clearChat,
    abortAgent,
  }
}

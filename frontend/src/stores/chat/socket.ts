import type { ComputedRef, Ref } from 'vue'
import {
  findRecentToolInput,
  resolveConversationAgentId,
  toAttachmentSnapshot,
} from './helpers'
import { normalizeArtifactKind } from './memory'
import type {
  AgentInfo,
  ChatMessage,
  ConversationItem,
  SendMessageOptions,
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
}: SocketDomainDeps) {
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
          agent_id: currentConversationId.value ? undefined : activeAgentId.value,
        }),
      )
    }

    wsState.current.onmessage = (event) => {
      const data = JSON.parse(event.data)

      switch (data.type) {
        case 'session':
          currentConversationId.value = data.conversation_id || null
          if (typeof data.agent_id === 'string' && data.agent_id.trim()) {
            draftAgentId.value = data.agent_id
          }
          break

        case 'text':
          messages.push({
            id: genId(),
            role: 'assistant',
            content: data.content,
            type: 'text',
            agentId: data.agent_id,
            timestamp: Date.now(),
          })
          break

        case 'text_delta': {
          const lastMessage = messages[messages.length - 1]
          if (lastMessage && lastMessage.role === 'assistant' && lastMessage.type === 'text') {
            lastMessage.content += data.content
            break
          }

          messages.push({
            id: genId(),
            role: 'assistant',
            content: data.content,
            type: 'text',
            agentId: data.agent_id,
            timestamp: Date.now(),
            streaming: true,
          })
          break
        }

        case 'thinking_delta': {
          const lastMessage = messages[messages.length - 1]
          if (lastMessage && lastMessage.role === 'assistant') {
            lastMessage.thinking = (lastMessage.thinking || '') + data.content
            break
          }

          messages.push({
            id: genId(),
            role: 'assistant',
            content: '',
            type: 'text',
            agentId: data.agent_id,
            timestamp: Date.now(),
            streaming: true,
            thinking: data.content,
          })
          break
        }

        case 'tool_call':
          messages.push({
            id: genId(),
            role: 'system',
            content: data.tool_desc || `正在执行 Tool: **${data.tool_name}**`,
            type: 'tool_call',
            agentId: data.agent_id,
            toolName: data.tool_name,
            toolDesc: data.tool_desc,
            toolInput: data.tool_input,
            timestamp: Date.now(),
          })
          break

        case 'tool_result': {
          const toolResultInput = data.tool_input || findRecentToolInput(messages, data.tool_name)
          messages.push({
            id: genId(),
            role: 'system',
            content: data.result,
            type: 'tool_result',
            agentId: data.agent_id,
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
          void fetchConversations()
          break

        case 'error':
          messages.push({
            id: genId(),
            role: 'system',
            content: data.content,
            type: 'error',
            agentId: data.agent_id,
            timestamp: Date.now(),
          })
          isLoading.value = false
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
      }
    }

    wsState.current.onclose = () => {
      const wasLoading = isLoading.value
      isConnected.value = false
      wsState.current = null

      if (wasLoading) {
        isLoading.value = false
        finishStreamingAssistantMessage(messages)
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
      draftAgentId.value,
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
        agent_id: currentConversationId.value ? undefined : nextAgentId,
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

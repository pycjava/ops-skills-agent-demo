import type {
  AgentInfo,
  ChatMessage,
  ConversationAttachment,
  ConversationAttachmentSnapshot,
  ConversationItem,
} from './types'

export const CHAT_ENTRY_AGENT_ID = 'router'

const AGENT_ID_ALIASES: Record<string, string> = {
  orchestrator: 'router',
  'general-purpose': 'general',
}

export function normalizeAgentId(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined

  const normalized = value.trim()
  if (!normalized) return undefined

  return AGENT_ID_ALIASES[normalized] || normalized
}

export async function readErrorMessage(res: Response, fallback: string): Promise<string> {
  try {
    const contentType = res.headers.get('content-type') || ''
    if (contentType.includes('application/json')) {
      const body = await res.json()
      if (typeof body?.detail === 'string' && body.detail.trim()) {
        return body.detail
      }
      if (typeof body?.error === 'string' && body.error.trim()) {
        return body.error
      }
    } else {
      const text = (await res.text()).trim()
      if (text) {
        return text
      }
    }
  } catch (_error) {
    // ignore parse failures and fall back below
  }

  return fallback
}

export function apiFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  return fetch(input, {
    ...init,
    credentials: 'include',
  })
}

export function getDefaultAgentId(agents: AgentInfo[]): string {
  return agents.find((agent) => agent.is_default)?.id || CHAT_ENTRY_AGENT_ID
}

export function resolveAgentId(agentId: string | null | undefined, agents: AgentInfo[]): string {
  const candidate = normalizeAgentId(agentId) || ''
  if (!candidate) {
    return getDefaultAgentId(agents)
  }

  if (agents.length === 0) {
    return candidate
  }

  return agents.some((agent) => agent.id === candidate) ? candidate : getDefaultAgentId(agents)
}

export function resolveConversationAgentId(
  convId: string | null | undefined,
  conversations: ConversationItem[],
  draftAgentId: string,
  agents: AgentInfo[],
): string {
  if (!convId) {
    return resolveAgentId(draftAgentId, agents)
  }

  const conversationAgentId = conversations.find((conversation) => conversation.id === convId)?.agent_id
  return resolveAgentId(conversationAgentId || draftAgentId, agents)
}

export function findRecentToolInput(
  messages: ChatMessage[],
  toolName?: string,
): Record<string, unknown> | undefined {
  if (!toolName) return undefined

  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (
      message?.type === 'tool_call' &&
      message.toolName === toolName &&
      message.toolInput
    ) {
      return message.toolInput
    }
  }

  return undefined
}

export function stripSystemHint(content: string): string {
  return content.replace(/<system_hint>[\s\S]*?<\/system_hint>/g, '').trim()
}

export function toAttachmentSnapshot(
  attachment: ConversationAttachment | ConversationAttachmentSnapshot,
): ConversationAttachmentSnapshot {
  return {
    id: attachment.id,
    conversation_id:
      'conversation_id' in attachment && typeof attachment.conversation_id === 'string'
        ? attachment.conversation_id
        : undefined,
    original_name: attachment.original_name,
    stored_name: attachment.stored_name,
    relative_path: attachment.relative_path,
    mime_type: attachment.mime_type,
    size_bytes: attachment.size_bytes,
    created_at: attachment.created_at,
  }
}

export function normalizeAttachmentSnapshots(
  attachments: ConversationAttachmentSnapshot[] | null | undefined,
): ConversationAttachmentSnapshot[] | undefined {
  if (!attachments || attachments.length === 0) {
    return undefined
  }

  return attachments.map((attachment) => toAttachmentSnapshot(attachment))
}

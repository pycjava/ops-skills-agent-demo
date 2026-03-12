import type { ComputedRef, Ref } from 'vue'
import { CHAT_ENTRY_AGENT_ID, readErrorMessage } from './helpers'
import type { AgentInfo, ConversationAttachment, ConversationItem } from './types'

interface AttachmentDomainDeps {
  backendUrl: string
  conversationAttachments: Ref<ConversationAttachment[]>
  attachmentError: Ref<string | null>
  isAttachmentUploading: Ref<boolean>
  deletingAttachmentIds: Ref<string[]>
  currentConversationId: Ref<string | null>
  draftAgentId: Ref<string>
  activeAgentId: ComputedRef<string>
  conversations: Ref<ConversationItem[]>
  agents: Ref<AgentInfo[]>
  wsState: { current: WebSocket | null }
  fetchConversations: () => Promise<void>
  fetchSkills: (agentId?: string) => Promise<void>
}

interface UploadAttachmentResponse {
  conversation: ConversationItem
  attachment: ConversationAttachment
}

function sendConversationInit(
  wsState: { current: WebSocket | null },
  conversationId: string,
  agentId: string,
) {
  if (!wsState.current || wsState.current.readyState !== WebSocket.OPEN) {
    return
  }

  wsState.current.send(
    JSON.stringify({
      type: 'init',
      conversation_id: conversationId,
      agent_id: agentId,
    }),
  )
}

function upsertConversation(
  conversations: Ref<ConversationItem[]>,
  nextConversation: ConversationItem,
) {
  const index = conversations.value.findIndex(
    (conversation) => conversation.id === nextConversation.id,
  )
  if (index === -1) {
    conversations.value = [nextConversation, ...conversations.value]
    return
  }

  conversations.value = conversations.value.map((conversation, conversationIndex) =>
    conversationIndex === index ? nextConversation : conversation,
  )
}

function upsertAttachment(
  attachments: ConversationAttachment[],
  nextAttachment: ConversationAttachment,
): ConversationAttachment[] {
  const index = attachments.findIndex((attachment) => attachment.id === nextAttachment.id)
  if (index === -1) {
    return [...attachments, nextAttachment]
  }

  return attachments.map((attachment, attachmentIndex) =>
    attachmentIndex === index ? nextAttachment : attachment,
  )
}

export function createAttachmentDomain({
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
  fetchConversations,
  fetchSkills,
}: AttachmentDomainDeps) {
  void agents

  async function fetchConversationAttachments(conversationId = currentConversationId.value) {
    if (!conversationId) {
      conversationAttachments.value = []
      attachmentError.value = null
      return
    }

    try {
      const res = await fetch(
        `${backendUrl}/api/conversations/${encodeURIComponent(conversationId)}/attachments`,
      )
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
      }
      conversationAttachments.value = await res.json()
      attachmentError.value = null
    } catch (error) {
      conversationAttachments.value = []
      attachmentError.value = error instanceof Error ? error.message : '加载附件失败'
      console.warn('加载会话附件失败:', error)
    }
  }

  function clearConversationAttachments() {
    conversationAttachments.value = []
    attachmentError.value = null
  }

  async function uploadConversationAttachment(file: File): Promise<boolean> {
    attachmentError.value = null
    isAttachmentUploading.value = true

    try {
      const previousConversationId = currentConversationId.value
      const formData = new FormData()
      formData.append('file', file)
      if (previousConversationId) {
        formData.append('conversation_id', previousConversationId)
      } else {
        void activeAgentId
        formData.append('agent_id', CHAT_ENTRY_AGENT_ID)
      }

      const res = await fetch(`${backendUrl}/api/conversations/attachments`, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
      }

      const payload = (await res.json()) as UploadAttachmentResponse
      const { conversation, attachment } = payload
      const needsRebind = previousConversationId !== conversation.id

      currentConversationId.value = conversation.id
      draftAgentId.value = conversation.agent_id || draftAgentId.value
      upsertConversation(conversations, conversation)
      conversationAttachments.value = needsRebind
        ? [attachment]
        : upsertAttachment(conversationAttachments.value, attachment)

      await fetchConversations()
      await fetchSkills(conversation.agent_id)

      if (needsRebind) {
        sendConversationInit(wsState, conversation.id, conversation.agent_id)
      }

      return true
    } catch (error) {
      attachmentError.value = error instanceof Error ? error.message : '上传附件失败'
      console.warn('上传会话附件失败:', error)
      return false
    } finally {
      isAttachmentUploading.value = false
    }
  }

  async function deleteConversationAttachment(attachmentId: string): Promise<boolean> {
    const conversationId = currentConversationId.value
    if (!conversationId) {
      return false
    }

    deletingAttachmentIds.value = [...deletingAttachmentIds.value, attachmentId]
    attachmentError.value = null

    try {
      const res = await fetch(
        `${backendUrl}/api/conversations/${encodeURIComponent(conversationId)}/attachments/${encodeURIComponent(attachmentId)}`,
        {
          method: 'DELETE',
        },
      )
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
      }

      conversationAttachments.value = conversationAttachments.value.filter(
        (attachment) => attachment.id !== attachmentId,
      )
      return true
    } catch (error) {
      attachmentError.value = error instanceof Error ? error.message : '删除附件失败'
      console.warn('删除会话附件失败:', error)
      return false
    } finally {
      deletingAttachmentIds.value = deletingAttachmentIds.value.filter((id) => id !== attachmentId)
    }
  }

  return {
    fetchConversationAttachments,
    clearConversationAttachments,
    uploadConversationAttachment,
    deleteConversationAttachment,
  }
}

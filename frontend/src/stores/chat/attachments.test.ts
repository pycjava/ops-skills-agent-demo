import { computed, ref } from 'vue'
import { createAttachmentDomain } from './attachments'
import type { AgentInfo, ConversationAttachment, ConversationItem } from './types'

function createFetchResponse(payload: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: async () => payload,
  } as Response
}

describe('createAttachmentDomain', () => {
  const originalFetch = global.fetch

  afterEach(() => {
    global.fetch = originalFetch
    vi.restoreAllMocks()
  })

  test('uploading in draft mode creates a conversation, stores the attachment, and rebinds websocket', async () => {
    const conversationAttachments = ref<ConversationAttachment[]>([])
    const attachmentError = ref<string | null>(null)
    const isAttachmentUploading = ref(false)
    const deletingAttachmentIds = ref<string[]>([])
    const currentConversationId = ref<string | null>(null)
    const draftAgentId = ref('dba')
    const conversations = ref<ConversationItem[]>([])
    const agents = ref<AgentInfo[]>([
      {
        id: 'dba',
        label: 'DBA',
        description: '',
        capabilities: [],
        is_default: false,
      },
    ])
    const wsState = {
      current: {
        readyState: WebSocket.OPEN,
        send: vi.fn(),
      } as Pick<WebSocket, 'readyState' | 'send'> as WebSocket,
    }
    const fetchConversations = vi.fn(async () => {})
    const fetchSkills = vi.fn(async () => {})
    let capturedBody: BodyInit | null | undefined

    global.fetch = vi.fn(async (_input, init) => {
      capturedBody = init?.body

      return createFetchResponse({
        conversation: {
          id: 'conv-1',
          title: '新对话',
          source: 'web',
          agent_id: 'orchestrator',
          created_at: null,
          updated_at: null,
        },
        attachment: {
          id: 'att-1',
          conversation_id: 'conv-1',
          original_name: 'sample.csv',
          stored_name: 'sample-1.csv',
          relative_path: 'data/conversation_attachments/conv-1/sample-1.csv',
          mime_type: 'text/csv',
          size_bytes: 12,
          created_at: '2026-03-10T10:00:00.000',
        },
      })
    }) as typeof fetch

    const domain = createAttachmentDomain({
      backendUrl: '',
      conversationAttachments,
      attachmentError,
      isAttachmentUploading,
      deletingAttachmentIds,
      currentConversationId,
      draftAgentId,
      activeAgentId: computed(() => draftAgentId.value),
      conversations,
      agents,
      wsState,
      fetchConversations,
      fetchSkills,
    })

    await domain.uploadConversationAttachment(
      new File(['id,name\n1,a\n'], 'sample.csv', { type: 'text/csv' }),
    )

    expect(currentConversationId.value).toBe('conv-1')
    expect(conversationAttachments.value).toHaveLength(1)
    expect(conversationAttachments.value[0]?.id).toBe('att-1')
    expect(capturedBody).toBeInstanceOf(FormData)
    expect((capturedBody as FormData).get('agent_id')).toBe('orchestrator')
    expect(fetchConversations).toHaveBeenCalledTimes(1)
    expect(fetchSkills).toHaveBeenCalledWith('orchestrator')
    expect(wsState.current.send).toHaveBeenCalledWith(
      JSON.stringify({
        type: 'init',
        conversation_id: 'conv-1',
        agent_id: 'orchestrator',
      }),
    )
  })

  test('deleting an attachment removes it from local state', async () => {
    const conversationAttachments = ref<ConversationAttachment[]>([
      {
        id: 'att-1',
        conversation_id: 'conv-1',
        original_name: 'sample.csv',
        stored_name: 'sample-1.csv',
        relative_path: 'data/conversation_attachments/conv-1/sample-1.csv',
        mime_type: 'text/csv',
        size_bytes: 12,
        created_at: '2026-03-10T10:00:00.000',
      },
    ])
    const attachmentError = ref<string | null>(null)
    const isAttachmentUploading = ref(false)
    const deletingAttachmentIds = ref<string[]>([])
    const currentConversationId = ref<string | null>('conv-1')
    const draftAgentId = ref('general')
    const conversations = ref<ConversationItem[]>([])
    const agents = ref<AgentInfo[]>([])
    const wsState = { current: null as WebSocket | null }

    global.fetch = vi.fn(async () => createFetchResponse({ ok: true })) as typeof fetch

    const domain = createAttachmentDomain({
      backendUrl: '',
      conversationAttachments,
      attachmentError,
      isAttachmentUploading,
      deletingAttachmentIds,
      currentConversationId,
      draftAgentId,
      activeAgentId: computed(() => draftAgentId.value),
      conversations,
      agents,
      wsState,
      fetchConversations: vi.fn(async () => {}),
      fetchSkills: vi.fn(async () => {}),
    })

    await domain.deleteConversationAttachment('att-1')

    expect(conversationAttachments.value).toEqual([])
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/conversations/conv-1/attachments/att-1',
      { method: 'DELETE', credentials: 'include' },
    )
  })
})

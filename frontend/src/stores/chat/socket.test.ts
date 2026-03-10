import { computed, ref } from 'vue'
import { createSocketDomain } from './socket'
import type {
  AgentInfo,
  ConversationAttachment,
  ConversationItem,
} from './types'

function createAttachment(overrides: Partial<ConversationAttachment> = {}): ConversationAttachment {
  return {
    id: 'att-1',
    conversation_id: 'conv-1',
    original_name: 'report-a.md',
    stored_name: 'report-a.md',
    relative_path: 'data/conversation_attachments/conv-1/report-a.md',
    mime_type: 'text/markdown',
    size_bytes: 120,
    created_at: '2026-03-10T10:00:00.000',
    ...overrides,
  }
}

describe('createSocketDomain', () => {
  test('sends attachment ids and stores attachment snapshot on the local user message', () => {
    const messages: Array<Record<string, unknown>> = []
    const conversations = ref<ConversationItem[]>([])
    const currentConversationId = ref<string | null>('conv-1')
    const draftAgentId = ref('general')
    const agents = ref<AgentInfo[]>([
      {
        id: 'general',
        label: '通用助手',
        description: '',
        capabilities: [],
        is_default: true,
      },
    ])
    const isConnected = ref(true)
    const isLoading = ref(false)
    const send = vi.fn()
    const wsState = {
      current: {
        readyState: WebSocket.OPEN,
        send,
      } as Pick<WebSocket, 'readyState' | 'send'> as WebSocket,
    }
    const attachment = createAttachment()

    const domain = createSocketDomain({
      wsUrl: 'ws://localhost/ws/chat',
      messages: messages as never[],
      conversations,
      currentConversationId,
      draftAgentId,
      activeAgentId: computed(() => 'general'),
      agents,
      isConnected,
      isLoading,
      wsState,
      genId: () => 'msg-1',
      fetchConversations: vi.fn(async () => {}),
      handleMemoryArtifact: vi.fn(),
    })

    domain.sendMessage('帮我合并汇总信息', '帮我合并汇总信息', {
      attachments: [attachment],
    })

    expect(messages).toEqual([
      expect.objectContaining({
        id: 'msg-1',
        role: 'user',
        content: '帮我合并汇总信息',
        type: 'text',
        attachments: [attachment],
      }),
    ])
    expect(send).toHaveBeenCalledWith(
      JSON.stringify({
        type: 'message',
        content: '帮我合并汇总信息',
        agent_id: undefined,
        attachment_ids: ['att-1'],
      }),
    )
  })
})

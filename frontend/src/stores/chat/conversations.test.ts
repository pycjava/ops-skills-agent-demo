import { computed, ref } from 'vue'
import { createConversationDomain } from './conversations'
import type { AgentInfo, ConversationItem } from './types'

function createFetchResponse(payload: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: async () => payload,
  } as Response
}

describe('createConversationDomain', () => {
  const originalFetch = global.fetch

  afterEach(() => {
    global.fetch = originalFetch
    vi.restoreAllMocks()
  })

  test('restores attachment snapshots from conversation history messages', async () => {
    const messages: Array<Record<string, unknown>> = []
    const conversations = ref<ConversationItem[]>([
      {
        id: 'conv-1',
        title: '新对话',
        source: 'web',
        agent_id: 'general',
        created_at: null,
        updated_at: null,
      },
    ])
    const currentConversationId = ref<string | null>(null)
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
    const isLoading = ref(false)
    const wsState = {
      current: {
        readyState: WebSocket.OPEN,
        send: vi.fn(),
      } as Pick<WebSocket, 'readyState' | 'send'> as WebSocket,
    }

    global.fetch = vi.fn(async () =>
      createFetchResponse([
        {
          id: 'msg-1',
          role: 'user',
          content: '帮我合并汇总信息',
          type: 'text',
          agent_id: 'general',
          tool_name: null,
          tool_input: null,
          attachments_snapshot: [
            {
              id: 'att-1',
              original_name: 'report-a.md',
              stored_name: 'report-a.md',
              relative_path: 'data/conversation_attachments/conv-1/report-a.md',
              mime_type: 'text/markdown',
              size_bytes: 120,
              created_at: '2026-03-10T10:00:00.000',
            },
          ],
          thinking: null,
          created_at: '2026-03-10T10:10:00.000',
        },
      ]),
    ) as typeof fetch

    const domain = createConversationDomain({
      backendUrl: '',
      messages: messages as never[],
      conversations,
      currentConversationId,
      draftAgentId,
      activeAgentId: computed(() => draftAgentId.value),
      agents,
      isLoading,
      wsState,
      fetchSkills: vi.fn(async () => {}),
    })

    await domain.switchConversation('conv-1')

    expect(messages).toEqual([
      expect.objectContaining({
        id: 'msg-1',
        role: 'user',
        content: '帮我合并汇总信息',
        attachments: [
          expect.objectContaining({
            id: 'att-1',
            original_name: 'report-a.md',
          }),
        ],
      }),
    ])
  })
})

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

function createStreamResponse(chunks: string[], ok = true, status = 200): Response {
  const encoder = new TextEncoder()

  return {
    ok,
    status,
    body: new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk))
        }
        controller.close()
      },
    }),
    text: async () => chunks.join(''),
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
        title: 'New Conversation',
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
        label: 'General',
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
          content: 'Summarize the attached reports',
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
        content: 'Summarize the attached reports',
        attachments: [
          expect.objectContaining({
            id: 'att-1',
            original_name: 'report-a.md',
          }),
        ],
      }),
    ])
  })

  test('streams a task run conversation and binds the websocket session after playback', async () => {
    const messages: Array<Record<string, unknown>> = []
    const conversations = ref<ConversationItem[]>([])
    const currentConversationId = ref<string | null>(null)
    const draftAgentId = ref('general')
    const agents = ref<AgentInfo[]>([
      {
        id: 'general',
        label: 'General',
        description: '',
        capabilities: [],
        is_default: true,
      },
      {
        id: 'dba',
        label: 'DBA',
        description: '',
        capabilities: [],
        is_default: false,
      },
    ])
    const isLoading = ref(false)
    const wsState = {
      current: {
        readyState: WebSocket.OPEN,
        send: vi.fn(),
      } as Pick<WebSocket, 'readyState' | 'send'> as WebSocket,
    }
    const fetchSkills = vi.fn(async () => {})

    global.fetch = vi
      .fn(async () =>
        createStreamResponse([
          'data: {"type":"history_start","run_id":"run-1","conversation_id":"conv-1","agent_id":"dba","title":"Peets Daily Inspection | 03-11 08:30","status":"succeeded"}\n\n',
          'data: {"type":"message","message":{"id":"msg-1","role":"system","content":"Running mysql check","type":"tool_call","agent_id":"dba","tool_name":"mysql_check","tool_input":{"instance":"peets-prod-pos-mysql"},"attachments_snapshot":null,"thinking":null,"created_at":"2026-03-10T10:10:00.000"}}\n\n',
          'data: {"type":"message","message":{"id":"msg-2","role":"system","content":"Mysql check complete","type":"tool_result","agent_id":"dba","tool_name":"mysql_check","tool_input":null,"attachments_snapshot":null,"thinking":null,"created_at":"2026-03-10T10:10:01.000"}}\n\n',
          'data: {"type":"history_done","run_id":"run-1","conversation_id":"conv-1"}\n\n',
          'data: {"type":"run_status","run_id":"run-1","conversation_id":"conv-1","status":"succeeded","finished_at":"2026-03-10T10:10:02.000","error_message":null}\n\n',
          'data: {"type":"done","run_id":"run-1","conversation_id":"conv-1","status":"succeeded"}\n\n',
        ]),
      )
      .mockImplementationOnce(async () =>
        createStreamResponse([
          'data: {"type":"history_start","run_id":"run-1","conversation_id":"conv-1","agent_id":"dba","title":"Peets Daily Inspection | 03-11 08:30","status":"succeeded"}\n\n',
          'data: {"type":"message","message":{"id":"msg-1","role":"system","content":"Running mysql check","type":"tool_call","agent_id":"dba","tool_name":"mysql_check","tool_input":{"instance":"peets-prod-pos-mysql"},"attachments_snapshot":null,"thinking":null,"created_at":"2026-03-10T10:10:00.000"}}\n\n',
          'data: {"type":"message","message":{"id":"msg-2","role":"system","content":"Mysql check complete","type":"tool_result","agent_id":"dba","tool_name":"mysql_check","tool_input":null,"attachments_snapshot":null,"thinking":null,"created_at":"2026-03-10T10:10:01.000"}}\n\n',
          'data: {"type":"history_done","run_id":"run-1","conversation_id":"conv-1"}\n\n',
          'data: {"type":"run_status","run_id":"run-1","conversation_id":"conv-1","status":"succeeded","finished_at":"2026-03-10T10:10:02.000","error_message":null}\n\n',
          'data: {"type":"done","run_id":"run-1","conversation_id":"conv-1","status":"succeeded"}\n\n',
        ]),
      )
      .mockImplementationOnce(async () =>
        createFetchResponse([
          {
            id: 'conv-1',
            title: 'Peets Daily Inspection | 03-11 08:30',
            source: 'task',
            agent_id: 'dba',
            created_at: null,
            updated_at: null,
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
      fetchSkills,
    })

    await domain.streamInspectionTaskRunConversation('run-1', 'conv-1')

    expect(currentConversationId.value).toBe('conv-1')
    expect(draftAgentId.value).toBe('dba')
    expect(fetchSkills).toHaveBeenCalledWith('dba')
    expect(wsState.current?.send).toHaveBeenCalledWith(
      JSON.stringify({
        type: 'init',
        conversation_id: 'conv-1',
        agent_id: 'dba',
      }),
    )
    expect(conversations.value).toEqual([
      expect.objectContaining({
        id: 'conv-1',
        title: 'Peets Daily Inspection | 03-11 08:30',
        source: 'task',
        agent_id: 'dba',
      }),
    ])
    expect(messages).toEqual([
      expect.objectContaining({
        id: 'msg-1',
        role: 'system',
        type: 'tool_call',
        toolName: 'mysql_check',
        toolInput: {
          instance: 'peets-prod-pos-mysql',
        },
      }),
      expect.objectContaining({
        id: 'msg-2',
        role: 'system',
        type: 'tool_result',
        toolName: 'mysql_check',
        toolInput: {
          instance: 'peets-prod-pos-mysql',
        },
      }),
    ])
    expect(isLoading.value).toBe(false)
  })
})

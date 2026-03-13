import { computed, ref } from 'vue'
import { createSocketDomain } from './socket'
import type {
  AgentInfo,
  ConversationAttachment,
  ConversationItem,
  TaskNotification,
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

function createNotification(
  overrides: Partial<TaskNotification> = {},
): TaskNotification {
  return {
    id: 'notification-1',
    task_id: 'task-1',
    task_run_id: 'run-1',
    conversation_id: 'conv-1',
    status: 'succeeded',
    title: 'Peets Daily Inspection',
    summary: 'Summary line 1\nSummary line 2',
    report_name: 'report-a.md',
    report_path: '/memories/reports/report-a.md',
    read_at: null,
    created_at: '2026-03-12T09:00:00.000',
    ...overrides,
  }
}

describe('createSocketDomain', () => {
  test('starts a new assistant bubble when streamed text switches agent', () => {
    const messages: Array<Record<string, unknown>> = []
    const conversations = ref<ConversationItem[]>([])
    const currentConversationId = ref<string | null>(null)
    const draftAgentId = ref('router')
    const agents = ref<AgentInfo[]>([
      {
        id: 'router',
        label: '智能编排助手',
        description: '',
        capabilities: [],
        is_default: true,
      },
      {
        id: 'dba',
        label: '数据库助手',
        description: '',
        capabilities: [],
        is_default: false,
      },
    ])
    const isConnected = ref(false)
    const isLoading = ref(false)
    const handleTaskNotificationEvent = vi.fn()
    const wsInstances: Array<{
      onopen: null | (() => void)
      onmessage: null | ((event: MessageEvent<string>) => void)
      onclose: null | (() => void)
      onerror: null | (() => void)
      readyState: number
      send: ReturnType<typeof vi.fn>
    }> = []

    class FakeWebSocket {
      static readonly CONNECTING = 0
      static readonly OPEN = 1
      static readonly CLOSING = 2
      static readonly CLOSED = 3

      onopen: null | (() => void) = null
      onmessage: null | ((event: MessageEvent<string>) => void) = null
      onclose: null | (() => void) = null
      onerror: null | (() => void) = null
      readyState = FakeWebSocket.OPEN
      send = vi.fn()

      constructor(_url: string) {
        wsInstances.push(this)
      }
    }

    vi.stubGlobal('WebSocket', FakeWebSocket)

    const wsState = { current: null as WebSocket | null }
    const domain = createSocketDomain({
      wsUrl: 'ws://localhost/ws/chat',
      messages: messages as never[],
      conversations,
      currentConversationId,
      draftAgentId,
      activeAgentId: computed(() => 'router'),
      agents,
      isConnected,
      isLoading,
      wsState,
      genId: (() => {
        let id = 0
        return () => `msg-${++id}`
      })(),
      fetchConversations: vi.fn(async () => {}),
      handleMemoryArtifact: vi.fn(),
      handleTaskNotificationEvent,
    })

    domain.connect()

    const socket = wsInstances[0]
    if (!socket?.onmessage) {
      throw new Error('socket onmessage handler was not registered')
    }

    socket.onmessage({
      data: JSON.stringify({
        type: 'text_delta',
        content: '正在为你分析问题。',
        agent_id: 'router',
      }),
    } as MessageEvent<string>)

    socket.onmessage({
      data: JSON.stringify({
        type: 'text_delta',
        content: '已定位到慢查询 SQL。',
        agent_id: 'dba',
      }),
    } as MessageEvent<string>)

    expect(messages).toEqual([
      expect.objectContaining({
        role: 'assistant',
        content: '正在为你分析问题。',
        agentId: 'router',
      }),
      expect.objectContaining({
        role: 'assistant',
        content: '已定位到慢查询 SQL。',
        agentId: 'dba',
      }),
    ])

    vi.unstubAllGlobals()
  })

  test('initializes a new websocket session with router even if the stale draft agent differs', () => {
    const messages: Array<Record<string, unknown>> = []
    const conversations = ref<ConversationItem[]>([])
    const currentConversationId = ref<string | null>(null)
    const draftAgentId = ref('dba')
    const agents = ref<AgentInfo[]>([
      {
        id: 'router',
        label: '智能编排助手',
        description: '',
        capabilities: [],
        is_default: true,
      },
      {
        id: 'dba',
        label: '数据库助手',
        description: '',
        capabilities: [],
        is_default: false,
      },
    ])
    const isConnected = ref(false)
    const isLoading = ref(false)
    const handleTaskNotificationEvent = vi.fn()
    const wsInstances: Array<{
      onopen: null | (() => void)
      onmessage: null | ((event: MessageEvent<string>) => void)
      onclose: null | (() => void)
      onerror: null | (() => void)
      readyState: number
      send: ReturnType<typeof vi.fn>
    }> = []

    class FakeWebSocket {
      static readonly CONNECTING = 0
      static readonly OPEN = 1
      static readonly CLOSING = 2
      static readonly CLOSED = 3

      onopen: null | (() => void) = null
      onmessage: null | ((event: MessageEvent<string>) => void) = null
      onclose: null | (() => void) = null
      onerror: null | (() => void) = null
      readyState = FakeWebSocket.OPEN
      send = vi.fn()

      constructor(_url: string) {
        wsInstances.push(this)
      }
    }

    vi.stubGlobal('WebSocket', FakeWebSocket)

    const wsState = { current: null as WebSocket | null }
    const domain = createSocketDomain({
      wsUrl: 'ws://localhost/ws/chat',
      messages: messages as never[],
      conversations,
      currentConversationId,
      draftAgentId,
      activeAgentId: computed(() => 'dba'),
      agents,
      isConnected,
      isLoading,
      wsState,
      genId: () => 'msg-1',
      fetchConversations: vi.fn(async () => {}),
      handleMemoryArtifact: vi.fn(),
      handleTaskNotificationEvent,
    })

    domain.connect()

    const socket = wsInstances[0]
    if (!socket?.onopen) {
      throw new Error('socket onopen handler was not registered')
    }

    socket.onopen()

    expect(socket.send).toHaveBeenCalledWith(
      JSON.stringify({
        type: 'init',
        conversation_id: null,
        agent_id: 'router',
      }),
    )
    vi.unstubAllGlobals()
  })

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
    const handleTaskNotificationEvent = vi.fn()
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
      handleTaskNotificationEvent,
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

  test('forwards realtime task notification events to the notification domain', () => {
    const messages: Array<Record<string, unknown>> = []
    const conversations = ref<ConversationItem[]>([])
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
    const isConnected = ref(false)
    const isLoading = ref(false)
    const handleTaskNotificationEvent = vi.fn()
    const wsInstances: Array<{
      onopen: null | (() => void)
      onmessage: null | ((event: MessageEvent<string>) => void)
      onclose: null | (() => void)
      onerror: null | (() => void)
      readyState: number
      send: ReturnType<typeof vi.fn>
    }> = []

    class FakeWebSocket {
      static readonly CONNECTING = 0
      static readonly OPEN = 1
      static readonly CLOSING = 2
      static readonly CLOSED = 3

      onopen: null | (() => void) = null
      onmessage: null | ((event: MessageEvent<string>) => void) = null
      onclose: null | (() => void) = null
      onerror: null | (() => void) = null
      readyState = FakeWebSocket.OPEN
      send = vi.fn()

      constructor(_url: string) {
        wsInstances.push(this)
      }
    }

    vi.stubGlobal('WebSocket', FakeWebSocket)

    const wsState = { current: null as WebSocket | null }
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
      handleTaskNotificationEvent,
    })

    domain.connect()

    const socket = wsInstances[0]
    if (!socket?.onmessage) {
      throw new Error('socket onmessage handler was not registered')
    }

    const notification = createNotification()
    socket.onmessage({
      data: JSON.stringify({
        type: 'task_notification',
        notification,
        unread_count: 3,
      }),
    } as MessageEvent<string>)

    expect(handleTaskNotificationEvent).toHaveBeenCalledWith(notification, 3)
    vi.unstubAllGlobals()
  })
})

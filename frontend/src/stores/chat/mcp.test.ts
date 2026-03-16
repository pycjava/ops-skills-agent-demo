import { ref } from 'vue'
import { createMcpDomain } from './mcp'
import type { McpServer } from './types'

function createFetchResponse(payload: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    headers: new Headers({
      'content-type': 'application/json',
    }),
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  } as Response
}

const weatherServer: McpServer = {
  id: 'weather',
  name: 'weather',
  transport: 'http',
  url: 'https://example.com/mcp',
  command: null,
  args: [],
  env: null,
  has_env: false,
  env_keys: [],
  enabled: true,
  agent_ids: ['general'],
  has_headers: false,
  header_keys: [],
  last_test_status: 'untested',
  last_tested_at: null,
  last_error: null,
  last_tools: [],
}

describe('createMcpDomain', () => {
  const originalFetch = global.fetch

  afterEach(() => {
    global.fetch = originalFetch
    vi.restoreAllMocks()
  })

  test('fetches the full mcp.json document and parsed server list', async () => {
    const mcpServers = ref<McpServer[]>([])
    const mcpConfigText = ref('')
    const isMcpLoading = ref(false)
    const mcpError = ref<string | null>(null)
    const testingServerIds = ref<string[]>([])

    global.fetch = vi.fn(async () =>
      createFetchResponse({
        config_text: '{\n  "mcpServers": {\n    "weather": {\n      "url": "https://example.com/mcp"\n    }\n  }\n}\n',
        servers: [weatherServer],
      }),
    ) as typeof fetch

    const domain = createMcpDomain({
      backendUrl: '',
      mcpServers,
      mcpConfigText,
      isMcpLoading,
      mcpError,
      testingServerIds,
    })

    await domain.fetchMcpConfig()

    expect(mcpConfigText.value).toContain('"mcpServers"')
    expect(mcpServers.value).toEqual([weatherServer])
  })

  test('saves the edited mcp.json document in one request', async () => {
    const mcpServers = ref<McpServer[]>([])
    const mcpConfigText = ref('')
    const isMcpLoading = ref(false)
    const mcpError = ref<string | null>(null)
    const testingServerIds = ref<string[]>([])

    global.fetch = vi.fn(async () =>
      createFetchResponse({
        config_text: '{\n  "mcpServers": {\n    "weather": {\n      "url": "https://api.example.com/mcp"\n    }\n  }\n}\n',
        servers: [
          {
            ...weatherServer,
            url: 'https://api.example.com/mcp',
          },
        ],
      }),
    ) as typeof fetch

    const domain = createMcpDomain({
      backendUrl: '',
      mcpServers,
      mcpConfigText,
      isMcpLoading,
      mcpError,
      testingServerIds,
    })

    const ok = await domain.saveMcpConfig(
      '{"mcpServers":{"weather":{"url":"https://api.example.com/mcp"}}}',
    )

    expect(ok).toBe(true)
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/mcp/config',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          config_text: '{"mcpServers":{"weather":{"url":"https://api.example.com/mcp"}}}',
        }),
      }),
    )
    expect(mcpServers.value[0]?.url).toBe('https://api.example.com/mcp')
    expect(mcpConfigText.value).toContain('api.example.com')
  })

  test('tests one server by name and merges the returned runtime status', async () => {
    const mcpServers = ref<McpServer[]>([weatherServer])
    const mcpConfigText = ref('{\n  "mcpServers": {}\n}\n')
    const isMcpLoading = ref(false)
    const mcpError = ref<string | null>(null)
    const testingServerIds = ref<string[]>([])

    global.fetch = vi.fn(async () =>
      createFetchResponse({
        ok: true,
        tested_at: '2026-03-13T12:00:00.000',
        error: null,
        tools: [{ name: 'forecast', description: 'Show forecast' }],
        server: {
          ...weatherServer,
          last_test_status: 'ok',
          last_tested_at: '2026-03-13T12:00:00.000',
          last_tools: [{ name: 'forecast', description: 'Show forecast' }],
        },
      }),
    ) as typeof fetch

    const domain = createMcpDomain({
      backendUrl: '',
      mcpServers,
      mcpConfigText,
      isMcpLoading,
      mcpError,
      testingServerIds,
    })

    const ok = await domain.testMcpServer('weather')

    expect(ok).toBe(true)
    expect(mcpServers.value[0]?.last_test_status).toBe('ok')
    expect(mcpServers.value[0]?.last_tools).toEqual([
      { name: 'forecast', description: 'Show forecast' },
    ])
  })
})

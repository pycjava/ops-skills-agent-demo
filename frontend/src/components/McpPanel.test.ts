import { mount } from '@vue/test-utils'
import McpPanel from './McpPanel.vue'

const saveMcpConfig = vi.fn(async () => true)
const testMcpServer = vi.fn(async () => true)

const chatStoreMock = {
  agents: [
    {
      id: 'general',
      label: 'General',
    },
  ],
  activeAgentId: 'general',
  mcpServers: [
    {
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
    },
  ],
  mcpConfigText: '{\n  "mcpServers": {\n    "weather": {\n      "url": "https://example.com/mcp"\n    }\n  }\n}\n',
  mcpError: null,
  isMcpLoading: false,
  testingServerIds: [],
  saveMcpConfig,
  testMcpServer,
}

vi.mock('../stores/chat', () => ({
  useChatStore: () => chatStoreMock,
}))

describe('McpPanel', () => {
  beforeEach(() => {
    saveMcpConfig.mockClear()
    testMcpServer.mockClear()
    chatStoreMock.mcpConfigText =
      '{\n  "mcpServers": {\n    "weather": {\n      "url": "https://example.com/mcp"\n    }\n  }\n}\n'
  })

  test('edits and saves the whole mcp.json document from one textarea', async () => {
    const wrapper = mount(McpPanel)

    const editor = wrapper.get('textarea.json-editor')
    expect((editor.element as HTMLTextAreaElement).value).toContain('"mcpServers"')

    await editor.setValue('{"mcpServers":{"weather":{"url":"https://api.example.com/mcp"}}}')
    await wrapper.get('button.save-config').trigger('click')

    expect(saveMcpConfig).toHaveBeenCalledWith(
      '{\n  "mcpServers": {\n    "weather": {\n      "url": "https://api.example.com/mcp"\n    }\n  }\n}\n',
    )
  })

  test('runs a server test from the parsed server summary list', async () => {
    const wrapper = mount(McpPanel)

    await wrapper.get('button.server-test').trigger('click')

    expect(testMcpServer).toHaveBeenCalledWith('weather')
  })
})

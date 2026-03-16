import type { Ref } from 'vue'
import { apiFetch, readErrorMessage } from './helpers'
import type { McpConfigResponse, McpServer, McpToolPreview } from './types'

interface McpDomainDeps {
  backendUrl: string
  mcpServers: Ref<McpServer[]>
  mcpConfigText: Ref<string>
  isMcpLoading: Ref<boolean>
  mcpError: Ref<string | null>
  testingServerIds: Ref<string[]>
}

function replaceMcpServer(mcpServers: Ref<McpServer[]>, server: McpServer) {
  const index = mcpServers.value.findIndex(
    (item) => item.id === server.id || item.name === server.name,
  )
  if (index === -1) {
    mcpServers.value = [server, ...mcpServers.value]
    return
  }

  mcpServers.value = mcpServers.value.map((item, itemIndex) =>
    itemIndex === index ? server : item,
  )
}

function applyConfigPayload(
  mcpServers: Ref<McpServer[]>,
  mcpConfigText: Ref<string>,
  payload: McpConfigResponse,
) {
  mcpConfigText.value = payload.config_text
  mcpServers.value = payload.servers
}

export function createMcpDomain({
  backendUrl,
  mcpServers,
  mcpConfigText,
  isMcpLoading,
  mcpError,
  testingServerIds,
}: McpDomainDeps) {
  async function fetchMcpConfig() {
    isMcpLoading.value = true
    mcpError.value = null

    try {
      const res = await apiFetch(`${backendUrl}/api/mcp/config`)
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
      }
      applyConfigPayload(mcpServers, mcpConfigText, (await res.json()) as McpConfigResponse)
    } catch (error) {
      mcpError.value = error instanceof Error ? error.message : '加载 MCP 配置失败'
      console.warn('加载 MCP 配置失败:', error)
    } finally {
      isMcpLoading.value = false
    }
  }

  async function saveMcpConfig(configText: string): Promise<boolean> {
    mcpError.value = null
    try {
      const res = await apiFetch(`${backendUrl}/api/mcp/config`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          config_text: configText,
        }),
      })
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
      }
      applyConfigPayload(mcpServers, mcpConfigText, (await res.json()) as McpConfigResponse)
      return true
    } catch (error) {
      mcpError.value = error instanceof Error ? error.message : '保存 MCP 配置失败'
      console.warn('保存 MCP 配置失败:', error)
      return false
    }
  }

  async function testMcpServer(serverName: string): Promise<boolean> {
    if (testingServerIds.value.includes(serverName)) {
      return false
    }

    testingServerIds.value = [...testingServerIds.value, serverName]
    mcpError.value = null

    try {
      const res = await apiFetch(
        `${backendUrl}/api/mcp/servers/${encodeURIComponent(serverName)}/test`,
        {
          method: 'POST',
        },
      )
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
      }

      const payload: {
        ok: boolean
        tested_at: string | null
        error?: string | null
        tools: McpToolPreview[]
        server?: McpServer
      } = await res.json()

      if (payload.server) {
        replaceMcpServer(mcpServers, payload.server)
      }
      if (!payload.ok) {
        mcpError.value = payload.error || 'MCP 服务测试失败'
      }

      return payload.ok
    } catch (error) {
      mcpError.value = error instanceof Error ? error.message : '测试 MCP 服务失败'
      console.warn('测试 MCP 服务失败:', error)
      return false
    } finally {
      testingServerIds.value = testingServerIds.value.filter((id) => id !== serverName)
    }
  }

  return {
    fetchMcpConfig,
    fetchMcpServers: fetchMcpConfig,
    saveMcpConfig,
    testMcpServer,
  }
}

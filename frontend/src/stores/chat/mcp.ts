import type { Ref } from 'vue'
import { readErrorMessage } from './helpers'
import type {
  McpServer,
  McpServerPayload,
  McpServerUpdatePayload,
  McpToolPreview,
} from './types'

interface McpDomainDeps {
  backendUrl: string
  mcpServers: Ref<McpServer[]>
  isMcpLoading: Ref<boolean>
  mcpError: Ref<string | null>
  testingServerIds: Ref<string[]>
}

function replaceMcpServer(mcpServers: Ref<McpServer[]>, server: McpServer) {
  const index = mcpServers.value.findIndex((item) => item.id === server.id)
  if (index === -1) {
    mcpServers.value = [server, ...mcpServers.value]
    return
  }

  mcpServers.value = mcpServers.value.map((item, itemIndex) =>
    itemIndex === index ? server : item,
  )
}

export function createMcpDomain({
  backendUrl,
  mcpServers,
  isMcpLoading,
  mcpError,
  testingServerIds,
}: McpDomainDeps) {
  async function fetchMcpServers() {
    isMcpLoading.value = true
    mcpError.value = null

    try {
      const res = await fetch(`${backendUrl}/api/mcp/servers`)
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
      }
      mcpServers.value = await res.json()
    } catch (error) {
      mcpError.value = error instanceof Error ? error.message : '加载 MCP 服务失败'
      console.warn('加载 MCP 服务失败:', error)
    } finally {
      isMcpLoading.value = false
    }
  }

  async function createMcpServer(payload: McpServerPayload): Promise<boolean> {
    mcpError.value = null
    try {
      const res = await fetch(`${backendUrl}/api/mcp/servers`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
      }
      await fetchMcpServers()
      return true
    } catch (error) {
      mcpError.value = error instanceof Error ? error.message : '创建 MCP 服务失败'
      console.warn('创建 MCP 服务失败:', error)
      return false
    }
  }

  async function updateMcpServer(
    serverId: string,
    payload: McpServerUpdatePayload,
  ): Promise<boolean> {
    mcpError.value = null
    try {
      const res = await fetch(`${backendUrl}/api/mcp/servers/${encodeURIComponent(serverId)}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
      }
      await fetchMcpServers()
      return true
    } catch (error) {
      mcpError.value = error instanceof Error ? error.message : '更新 MCP 服务失败'
      console.warn('更新 MCP 服务失败:', error)
      return false
    }
  }

  async function deleteMcpServer(serverId: string): Promise<boolean> {
    mcpError.value = null
    try {
      const res = await fetch(`${backendUrl}/api/mcp/servers/${encodeURIComponent(serverId)}`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
      }
      await fetchMcpServers()
      return true
    } catch (error) {
      mcpError.value = error instanceof Error ? error.message : '删除 MCP 服务失败'
      console.warn('删除 MCP 服务失败:', error)
      return false
    }
  }

  async function testMcpServer(serverId: string): Promise<boolean> {
    if (testingServerIds.value.includes(serverId)) {
      return false
    }

    testingServerIds.value = [...testingServerIds.value, serverId]
    mcpError.value = null

    try {
      const res = await fetch(
        `${backendUrl}/api/mcp/servers/${encodeURIComponent(serverId)}/test`,
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
      testingServerIds.value = testingServerIds.value.filter((id) => id !== serverId)
    }
  }

  return {
    fetchMcpServers,
    createMcpServer,
    updateMcpServer,
    deleteMcpServer,
    testMcpServer,
  }
}

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useChatStore } from '../stores/chat'
import type {
  McpServer,
  McpServerPayload,
  McpServerUpdatePayload,
  McpTransport,
} from '../stores/chat'

type EditableMcpConfig = {
  name: string
  transport: McpTransport
  url: string
  agent_ids: string[]
  headers?: Record<string, string>
}

const chatStore = useChatStore()

const isEditorOpen = ref(false)
const editingServer = ref<McpServer | null>(null)
const rawConfig = ref('')
const formError = ref('')

const activeAgent = computed(
  () => chatStore.agents.find((agent) => agent.id === chatStore.activeAgentId) ?? null,
)

const sortedServers = computed(() =>
  [...chatStore.mcpServers].sort((left, right) => {
    const leftTime = left.updated_at ? new Date(left.updated_at).getTime() : 0
    const rightTime = right.updated_at ? new Date(right.updated_at).getTime() : 0
    return rightTime - leftTime
  }),
)

const editorTitle = computed(() =>
  editingServer.value ? 'Edit MCP Server' : 'Add MCP Server',
)

const editorSubtitle = computed(() =>
  editingServer.value
    ? 'Edit the raw JSON config. Enable state is managed from the MCP list.'
    : 'Paste a raw JSON config. New servers are enabled by default and can be toggled from the list.',
)

const storedHeadersHint = computed(() => {
  const server = editingServer.value
  if (!server?.has_headers) return ''
  const keys = server.header_keys.length ? server.header_keys.join(', ') : 'masked headers'
  return `Stored headers: ${keys}. Omit "headers" to keep them, or provide a new "headers" object to replace them.`
})

function createTemplate(agentId: string): string {
  const payload: EditableMcpConfig = {
    name: 'weather',
    transport: 'http',
    url: 'https://example.com/mcp',
    agent_ids: [agentId],
  }
  return JSON.stringify(payload, null, 2)
}

function serializeServer(server: McpServer): string {
  const payload: EditableMcpConfig = {
    name: server.name,
    transport: server.transport,
    url: server.url,
    agent_ids: [...server.agent_ids],
  }
  return JSON.stringify(payload, null, 2)
}

function resetEditor() {
  editingServer.value = null
  rawConfig.value = ''
  formError.value = ''
}

function openCreateModal() {
  const fallbackAgentId = activeAgent.value?.id || chatStore.agents[0]?.id || 'general'
  resetEditor()
  rawConfig.value = createTemplate(fallbackAgentId)
  isEditorOpen.value = true
}

function openEditModal(server: McpServer) {
  resetEditor()
  editingServer.value = server
  rawConfig.value = serializeServer(server)
  isEditorOpen.value = true
}

function closeEditor() {
  isEditorOpen.value = false
  resetEditor()
}

function formatRawConfig() {
  try {
    const parsed = JSON.parse(rawConfig.value)
    rawConfig.value = JSON.stringify(parsed, null, 2)
    formError.value = ''
  } catch (_error) {
    formError.value = 'Invalid JSON. Fix the syntax before formatting.'
  }
}

function normalizeHeaders(value: unknown): Record<string, string> {
  if (value === undefined) {
    return {}
  }
  if (!value || Array.isArray(value) || typeof value !== 'object') {
    throw new Error('"headers" must be a JSON object.')
  }

  const normalized: Record<string, string> = {}
  for (const [rawKey, rawValue] of Object.entries(value)) {
    const key = String(rawKey || '').trim()
    if (!key) continue
    normalized[key] = String(rawValue ?? '')
  }
  return normalized
}

function parseEditorConfig(): {
  payload: EditableMcpConfig
  replaceHeaders: boolean
} | null {
  let parsed: unknown

  try {
    parsed = JSON.parse(rawConfig.value)
  } catch (_error) {
    formError.value = 'Invalid JSON. Please fix the syntax first.'
    return null
  }

  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    formError.value = 'The config must be a JSON object.'
    return null
  }

  const data = parsed as Record<string, unknown>
  const name = typeof data.name === 'string' ? data.name.trim() : ''
  const transport = data.transport
  const url = typeof data.url === 'string' ? data.url.trim() : ''
  const rawAgentIds = Array.isArray(data.agent_ids) ? data.agent_ids : []
  const agent_ids = [...new Set(rawAgentIds.map((value) => String(value || '').trim()).filter(Boolean))]

  if (!name) {
    formError.value = '"name" is required.'
    return null
  }
  if (transport !== 'http' && transport !== 'sse') {
    formError.value = '"transport" must be "http" or "sse".'
    return null
  }
  if (!url) {
    formError.value = '"url" is required.'
    return null
  }
  if (agent_ids.length === 0) {
    formError.value = '"agent_ids" must contain at least one agent id.'
    return null
  }

  try {
    const replaceHeaders = Object.prototype.hasOwnProperty.call(data, 'headers')
    const headers = normalizeHeaders(data.headers)

    formError.value = ''
    return {
      payload: {
        name,
        transport,
        url,
        agent_ids,
        ...(replaceHeaders ? { headers } : {}),
      },
      replaceHeaders,
    }
  } catch (error) {
    formError.value = error instanceof Error ? error.message : 'Invalid headers config.'
    return null
  }
}

async function submitConfig() {
  const parsed = parseEditorConfig()
  if (!parsed) return

  let ok = false

  if (editingServer.value) {
    const payload: McpServerUpdatePayload = {
      name: parsed.payload.name,
      transport: parsed.payload.transport,
      url: parsed.payload.url,
      enabled: editingServer.value.enabled,
      agent_ids: parsed.payload.agent_ids,
      replace_headers: parsed.replaceHeaders,
      ...(parsed.replaceHeaders ? { headers: parsed.payload.headers ?? {} } : {}),
    }
    ok = await chatStore.updateMcpServer(editingServer.value.id, payload)
  } else {
    const payload: McpServerPayload = {
      name: parsed.payload.name,
      transport: parsed.payload.transport,
      url: parsed.payload.url,
      enabled: true,
      agent_ids: parsed.payload.agent_ids,
      ...(parsed.replaceHeaders ? { headers: parsed.payload.headers ?? {} } : {}),
    }
    ok = await chatStore.createMcpServer(payload)
  }

  if (ok) {
    closeEditor()
  }
}

async function toggleEnabled(server: McpServer, enabled: boolean) {
  await chatStore.updateMcpServer(server.id, {
    name: server.name,
    transport: server.transport,
    url: server.url,
    enabled,
    agent_ids: server.agent_ids,
    replace_headers: false,
  })
}

async function toggleAgent(server: McpServer, agentId: string, checked: boolean) {
  const nextAgentIds = checked
    ? [...new Set([...server.agent_ids, agentId])]
    : server.agent_ids.filter((id) => id !== agentId)

  if (nextAgentIds.length === 0) {
    window.alert('Select at least one agent')
    return
  }

  await chatStore.updateMcpServer(server.id, {
    name: server.name,
    transport: server.transport,
    url: server.url,
    enabled: server.enabled,
    agent_ids: nextAgentIds,
    replace_headers: false,
  })
}

async function handleDelete(server: McpServer) {
  const confirmed = window.confirm(`Delete MCP server "${server.name}"?`)
  if (!confirmed) return
  await chatStore.deleteMcpServer(server.id)
}

function readChecked(event: Event) {
  return Boolean((event.target as HTMLInputElement | null)?.checked)
}

function isTesting(serverId: string) {
  return chatStore.testingServerIds.includes(serverId)
}

function formatTime(value: string | null) {
  if (!value) return 'Never'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function statusLabel(server: McpServer) {
  if (server.last_test_status === 'ok') return 'Healthy'
  if (server.last_test_status === 'error') return 'Error'
  return 'Untested'
}

function statusClass(server: McpServer) {
  return `status-${server.last_test_status}`
}

function isActiveForCurrentAgent(server: McpServer) {
  return server.agent_ids.includes(chatStore.activeAgentId)
}

function activeBoundAgents(server: McpServer) {
  return chatStore.agents.filter((agent) => server.agent_ids.includes(agent.id))
}

function hasStoredHeaders(server: McpServer) {
  return server.has_headers && server.header_keys.length > 0
}

function headerSummary(server: McpServer) {
  if (!server.header_keys.length) return 'Stored and masked'
  return server.header_keys.join(', ')
}
</script>

<template>
  <div class="panel">
    <div class="toolbar">
      <div>
        <div class="title">MCP Servers</div>
        <div class="subtitle">
          Current agent:
          <strong>{{ activeAgent?.label || chatStore.activeAgentId }}</strong>
        </div>
      </div>
      <button class="action-btn primary" @click="openCreateModal">Add Server</button>
    </div>

    <div v-if="chatStore.mcpError" class="banner error">
      {{ chatStore.mcpError }}
    </div>

    <div v-if="chatStore.isMcpLoading && sortedServers.length === 0" class="panel-empty">
      <span class="dim">loading mcp servers...</span>
    </div>

    <div v-else-if="sortedServers.length === 0" class="panel-empty">
      <span class="dim">no mcp servers configured</span>
    </div>

    <div v-else class="server-list">
      <section
        v-for="server in sortedServers"
        :key="server.id"
        class="server-card"
        :class="{ active: isActiveForCurrentAgent(server) }"
      >
        <div class="server-head">
          <div class="server-meta">
            <div class="name-row">
              <span class="server-name">{{ server.name }}</span>
              <span class="status-pill" :class="statusClass(server)">
                {{ statusLabel(server) }}
              </span>
              <span v-if="isActiveForCurrentAgent(server)" class="scope-pill">
                Active Agent
              </span>
            </div>
            <div class="server-url">{{ server.transport.toUpperCase() }} · {{ server.url }}</div>
          </div>

          <label class="toggle toggle-inline">
            <input
              type="checkbox"
              :checked="server.enabled"
              @change="toggleEnabled(server, readChecked($event))"
            />
            <span>{{ server.enabled ? 'Enabled' : 'Disabled' }}</span>
          </label>
        </div>

        <div class="meta-grid">
          <div class="meta-block">
            <div class="meta-label">Bound Agents</div>
            <div class="agent-list">
              <label
                v-for="agent in chatStore.agents"
                :key="`${server.id}-${agent.id}`"
                class="agent-chip"
                :class="{
                  selected: server.agent_ids.includes(agent.id),
                  current: agent.id === chatStore.activeAgentId,
                }"
              >
                <input
                  type="checkbox"
                  :checked="server.agent_ids.includes(agent.id)"
                  @change="toggleAgent(server, agent.id, readChecked($event))"
                />
                <span>{{ agent.label }}</span>
              </label>
            </div>
          </div>

          <div class="meta-block">
            <div class="meta-label">Headers</div>
            <div class="meta-text">
              {{ hasStoredHeaders(server) ? headerSummary(server) : 'No custom headers' }}
            </div>
          </div>

          <div class="meta-block">
            <div class="meta-label">Last Test</div>
            <div class="meta-text">{{ formatTime(server.last_tested_at) }}</div>
            <div v-if="server.last_error" class="error-text">{{ server.last_error }}</div>
          </div>
        </div>

        <div v-if="activeBoundAgents(server).length > 0" class="bound-summary">
          <span class="summary-label">Selected:</span>
          <span
            v-for="agent in activeBoundAgents(server)"
            :key="`${server.id}-summary-${agent.id}`"
            class="summary-chip"
            :class="{ current: agent.id === chatStore.activeAgentId }"
          >
            {{ agent.label }}
          </span>
        </div>

        <div class="tool-block">
          <div class="meta-label">Tools Preview</div>
          <div v-if="server.last_tools.length === 0" class="meta-text">
            No cached tool list. Run test to discover tools.
          </div>
          <div v-else class="tool-list">
            <div
              v-for="tool in server.last_tools"
              :key="`${server.id}-${tool.name}`"
              class="tool-item"
            >
              <div class="tool-name">{{ tool.name }}</div>
              <div class="tool-desc">{{ tool.description || 'No description' }}</div>
            </div>
          </div>
        </div>

        <div class="actions">
          <button
            class="action-btn"
            :disabled="isTesting(server.id)"
            @click="chatStore.testMcpServer(server.id)"
          >
            {{ isTesting(server.id) ? 'Testing...' : 'Test' }}
          </button>
          <button class="action-btn" @click="openEditModal(server)">Edit JSON</button>
          <button class="action-btn danger" @click="handleDelete(server)">Delete</button>
        </div>
      </section>
    </div>

    <div v-if="isEditorOpen" class="modal-backdrop" @click.self="closeEditor">
      <div class="modal">
        <div class="modal-head">
          <div class="modal-head-copy">
            <div class="title modal-title">{{ editorTitle }}</div>
            <div class="subtitle modal-subtitle">{{ editorSubtitle }}</div>
          </div>
          <button class="icon-btn icon-btn-close" aria-label="Close" @click="closeEditor">
            ×
          </button>
        </div>

        <div class="editor-toolbar">
          <div class="editor-info">
            <div class="meta-label">Raw Config</div>
            <div class="section-subtitle">
              Required keys: `name`, `transport`, `url`, `agent_ids`. Optional: `headers`.
            </div>
          </div>
          <button class="mini-btn" @click="formatRawConfig">Format JSON</button>
        </div>

        <div v-if="storedHeadersHint" class="masked-box">
          {{ storedHeadersHint }}
        </div>

        <textarea
          v-model="rawConfig"
          class="json-editor"
          spellcheck="false"
          autocomplete="off"
          autocorrect="off"
          autocapitalize="off"
        />

        <div v-if="formError" class="banner error">{{ formError }}</div>

        <div class="modal-actions">
          <button class="action-btn" @click="closeEditor">Cancel</button>
          <button class="action-btn primary" @click="submitConfig">
            {{ editingServer ? 'Save Config' : 'Create Server' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.panel {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  overflow-y: auto;
}

.toolbar,
.server-head,
.actions,
.modal-head,
.modal-actions,
.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-strong);
}

.subtitle,
.meta-text,
.server-url,
.tool-desc,
.section-subtitle,
.dim {
  font-size: 12px;
  color: var(--text-muted);
}

.panel-empty {
  padding: 20px 8px;
  text-align: center;
}

.server-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.server-card {
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 15px;
  background: color-mix(in srgb, var(--card) 82%, transparent);
  box-shadow: 0 8px 24px rgba(15, 18, 28, 0.04);
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    background 0.18s ease;
}

.server-card:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  box-shadow: 0 14px 32px rgba(15, 18, 28, 0.08);
}

.server-card.active {
  border-color: rgba(139, 115, 255, 0.35);
  box-shadow:
    0 0 0 1px rgba(139, 115, 255, 0.14),
    0 16px 36px rgba(139, 115, 255, 0.08);
}

.server-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.server-name,
.tool-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-strong);
}

.status-pill,
.scope-pill,
.summary-chip {
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
}

.status-pill {
  border: 1px solid var(--border);
}

.status-untested {
  color: var(--text-muted);
}

.status-ok {
  color: var(--success);
  border-color: rgba(113, 147, 111, 0.26);
  background: rgba(113, 147, 111, 0.08);
}

.status-error {
  color: var(--danger);
  border-color: rgba(200, 111, 100, 0.28);
  background: rgba(200, 111, 100, 0.08);
}

.scope-pill,
.summary-chip.current,
.agent-chip.current {
  color: var(--accent);
  background: rgba(139, 115, 255, 0.1);
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.meta-block,
.tool-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.meta-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.agent-list,
.bound-summary,
.tool-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.agent-chip {
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 6px 10px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
  background: color-mix(in srgb, var(--card) 74%, transparent);
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    color 0.16s ease,
    transform 0.16s ease;
}

.agent-chip:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  background: color-mix(in srgb, var(--card-strong) 88%, transparent);
}

.agent-chip.selected {
  border-color: var(--border-strong);
  color: var(--text-strong);
  background: color-mix(in srgb, var(--accent) 10%, var(--card));
}

.agent-chip input,
.toggle input {
  accent-color: var(--accent);
}

.summary-label {
  font-size: 12px;
  color: var(--text-muted);
}

.tool-item {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: color-mix(in srgb, var(--card-strong) 76%, transparent);
}

.actions {
  justify-content: flex-end;
}

.action-btn,
.mini-btn,
.icon-btn {
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--card-strong) 70%, transparent);
  color: var(--text-strong);
  border-radius: 12px;
  cursor: pointer;
  transition:
    transform 0.16s ease,
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease,
    color 0.16s ease;
}

.action-btn:hover,
.mini-btn:hover,
.icon-btn:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  background: color-mix(in srgb, var(--card-strong) 92%, transparent);
}

.action-btn {
  padding: 8px 14px;
  font-size: 12px;
}

.action-btn.primary {
  border-color: rgba(139, 115, 255, 0.28);
  background: linear-gradient(135deg, rgba(139, 115, 255, 0.18), rgba(139, 115, 255, 0.1));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.16);
}

.action-btn.danger {
  color: var(--danger);
}

.action-btn:disabled,
.mini-btn:disabled,
.icon-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.mini-btn,
.icon-btn {
  padding: 6px 10px;
  font-size: 12px;
}

.icon-btn-close {
  width: 40px;
  height: 40px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  border-radius: 14px;
}

.toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: color-mix(in srgb, var(--card-strong) 82%, transparent);
}

.toggle-inline {
  white-space: nowrap;
}

.banner {
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 12px;
}

.banner.error,
.error-text {
  color: var(--danger);
}

.banner.error {
  border: 1px solid rgba(200, 111, 100, 0.2);
  background: rgba(200, 111, 100, 0.08);
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(12, 12, 18, 0.5);
  backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 20;
}

.modal {
  width: min(760px, 100%);
  max-height: min(90vh, 780px);
  overflow-y: auto;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--card) 96%, white 4%),
      color-mix(in srgb, var(--card) 98%, transparent)
    ),
    var(--card);
  border: 1px solid color-mix(in srgb, var(--border-strong) 70%, transparent);
  border-radius: 28px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  box-shadow:
    0 28px 72px rgba(14, 18, 28, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.modal-head {
  padding-bottom: 14px;
  border-bottom: 1px solid color-mix(in srgb, var(--border) 90%, transparent);
}

.modal-head-copy,
.editor-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.modal-title {
  font-size: 28px;
  letter-spacing: -0.02em;
}

.modal-subtitle {
  font-size: 13px;
}

.json-editor {
  width: 100%;
  min-height: 360px;
  padding: 18px 20px;
  border: 1px solid var(--border);
  border-radius: 18px;
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--card-strong) 94%, transparent), color-mix(in srgb, var(--card) 90%, transparent));
  color: var(--text-strong);
  font:
    13px/1.7 'SFMono-Regular',
    Consolas,
    'Liberation Mono',
    Menlo,
    monospace;
  resize: vertical;
  outline: none;
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease,
    background 0.16s ease;
}

.json-editor:focus {
  border-color: rgba(139, 115, 255, 0.38);
  box-shadow: 0 0 0 4px rgba(139, 115, 255, 0.12);
}

.masked-box {
  border: 1px dashed var(--border);
  border-radius: 16px;
  padding: 14px 16px;
  font-size: 12px;
  color: var(--text-muted);
  background: color-mix(in srgb, var(--card-strong) 76%, transparent);
}

.modal-actions {
  padding-top: 14px;
  border-top: 1px solid color-mix(in srgb, var(--border) 90%, transparent);
}

@media (max-width: 720px) {
  .toolbar,
  .server-head,
  .actions,
  .modal-head,
  .modal-actions,
  .editor-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .modal {
    padding: 18px;
    border-radius: 22px;
  }

  .modal-title {
    font-size: 22px;
  }

  .json-editor {
    min-height: 300px;
  }
}
</style>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useChatStore } from '../stores/chat'
import { resolveKnownAgentLabel } from '../stores/chat/helpers'

const chatStore = useChatStore()
const rawConfig = ref('')
const formError = ref('')

const activeAgent = computed(
  () => chatStore.agents.find((agent) => agent.id === chatStore.activeAgentId) ?? null,
)
const activeAgentLabel = computed(
  () => activeAgent.value?.label || resolveKnownAgentLabel(chatStore.activeAgentId) || chatStore.activeAgentId,
)

const sortedServers = computed(() =>
  [...chatStore.mcpServers].sort((left, right) => left.name.localeCompare(right.name)),
)

watch(
  () => chatStore.mcpConfigText,
  (value) => {
    rawConfig.value = value || '{\n  "mcpServers": {}\n}\n'
  },
  { immediate: true },
)

function formatRawConfig() {
  try {
    const parsed = JSON.parse(rawConfig.value)
    rawConfig.value = `${JSON.stringify(parsed, null, 2)}\n`
    formError.value = ''
  } catch (_error) {
    formError.value = 'Invalid JSON. Fix the syntax before formatting.'
  }
}

async function saveConfig() {
  try {
    const parsed = JSON.parse(rawConfig.value)
    const formatted = `${JSON.stringify(parsed, null, 2)}\n`
    rawConfig.value = formatted
    formError.value = ''
    await chatStore.saveMcpConfig(formatted)
  } catch (_error) {
    formError.value = 'Invalid JSON. Please fix the syntax first.'
  }
}

function isTesting(serverName: string) {
  return chatStore.testingServerIds.includes(serverName)
}

function formatTime(value: string | null) {
  if (!value) return 'Never'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function statusLabel(status: string) {
  if (status === 'ok') return 'Healthy'
  if (status === 'error') return 'Error'
  return 'Untested'
}

function connectionSummary(server: {
  transport: string
  url: string | null
  command: string | null
  args: string[]
}) {
  if (server.transport === 'stdio') {
    const args = server.args.length ? ` ${server.args.join(' ')}` : ''
    return `${server.command || 'unknown'}${args}`
  }
  return server.url || 'unknown'
}
</script>

<template>
  <div class="panel">
    <div class="toolbar">
      <div>
        <div class="title">MCP Config</div>
        <div class="subtitle">
          Current agent:
          <strong>{{ activeAgentLabel }}</strong>
        </div>
      </div>
      <button class="action-btn primary save-config" @click="saveConfig">Save Config</button>
    </div>

    <div v-if="chatStore.mcpError" class="banner error">
      {{ chatStore.mcpError }}
    </div>

    <div class="editor-toolbar">
      <div class="editor-copy">
        <div class="meta-label">mcp.json</div>
        <div class="section-subtitle">
          Cursor-style JSON config with a top-level `mcpServers` object. Project-specific
          fields like `enabled` and `agentIds` are supported.
        </div>
      </div>
      <button class="mini-btn format-config" @click="formatRawConfig">Format JSON</button>
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

    <div class="server-summary">
      <div class="summary-head">
        <div class="title">Parsed Servers</div>
        <div class="subtitle">These are derived from the current editor content after save.</div>
      </div>

      <div v-if="chatStore.isMcpLoading && sortedServers.length === 0" class="panel-empty">
        <span class="dim">loading mcp config...</span>
      </div>

      <div v-else-if="sortedServers.length === 0" class="panel-empty">
        <span class="dim">no mcp servers configured</span>
      </div>

      <div v-else class="server-list">
        <section v-for="server in sortedServers" :key="server.name" class="server-card">
          <div class="server-head">
            <div class="server-meta">
              <div class="name-row">
                <span class="server-name">{{ server.name }}</span>
                <span class="status-pill" :class="`status-${server.last_test_status}`">
                  {{ statusLabel(server.last_test_status) }}
                </span>
              </div>
              <div class="server-url">
                {{ server.transport.toUpperCase() }} · {{ connectionSummary(server) }}
              </div>
            </div>

            <button
              class="action-btn server-test"
              :disabled="isTesting(server.name)"
              @click="chatStore.testMcpServer(server.name)"
            >
              {{ isTesting(server.name) ? 'Testing...' : 'Test' }}
            </button>
          </div>

          <div class="meta-grid">
            <div class="meta-block">
              <div class="meta-label">Enabled</div>
              <div class="meta-text">{{ server.enabled ? 'Yes' : 'No' }}</div>
            </div>

            <div class="meta-block">
              <div class="meta-label">Agent Binding</div>
              <div class="meta-text">
                {{ server.agent_ids.length > 0 ? server.agent_ids.join(', ') : 'All agents' }}
              </div>
            </div>

            <div class="meta-block">
              <div class="meta-label">Last Test</div>
              <div class="meta-text">{{ formatTime(server.last_tested_at) }}</div>
              <div v-if="server.last_error" class="error-text">{{ server.last_error }}</div>
            </div>
          </div>

          <div class="tool-block">
            <div class="meta-label">Tools Preview</div>
            <div v-if="server.last_tools.length === 0" class="meta-text">
              No cached tool list. Run test to discover tools.
            </div>
            <div v-else class="tool-list">
              <div v-for="tool in server.last_tools" :key="`${server.name}-${tool.name}`" class="tool-item">
                <div class="tool-name">{{ tool.name }}</div>
                <div class="tool-desc">{{ tool.description || 'No description' }}</div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.panel {
  height: 100%;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar,
.editor-toolbar,
.server-head {
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
.section-subtitle,
.meta-text,
.tool-desc,
.server-url,
.dim {
  font-size: 12px;
  color: var(--text-muted);
}

.editor-copy,
.server-meta,
.meta-block,
.tool-block,
.summary-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meta-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.json-editor {
  width: 100%;
  min-height: 320px;
  resize: vertical;
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: color-mix(in srgb, var(--card-strong) 94%, transparent);
  color: var(--text-strong);
  font:
    13px/1.7 'SFMono-Regular',
    Consolas,
    'Liberation Mono',
    Menlo,
    monospace;
  outline: none;
}

.json-editor:focus {
  border-color: rgba(139, 115, 255, 0.38);
  box-shadow: 0 0 0 4px rgba(139, 115, 255, 0.12);
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

.action-btn,
.mini-btn {
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--card-strong) 70%, transparent);
  color: var(--text-strong);
  border-radius: 12px;
  cursor: pointer;
  transition:
    transform 0.16s ease,
    border-color 0.16s ease,
    background 0.16s ease;
}

.action-btn:hover,
.mini-btn:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  background: color-mix(in srgb, var(--card-strong) 92%, transparent);
}

.action-btn:disabled,
.mini-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.action-btn {
  padding: 8px 14px;
  font-size: 12px;
}

.action-btn.primary {
  border-color: rgba(139, 115, 255, 0.28);
  background: linear-gradient(135deg, rgba(139, 115, 255, 0.18), rgba(139, 115, 255, 0.1));
}

.mini-btn {
  padding: 6px 10px;
  font-size: 12px;
}

.server-summary {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-empty {
  padding: 16px 8px;
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
  padding: 14px;
  background: color-mix(in srgb, var(--card) 84%, transparent);
  display: flex;
  flex-direction: column;
  gap: 12px;
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

.status-pill {
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
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

.meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.tool-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tool-item {
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 10px;
  background: color-mix(in srgb, var(--card-strong) 76%, transparent);
}

@media (max-width: 720px) {
  .toolbar,
  .editor-toolbar,
  .server-head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>

export type ArtifactKind = 'memory' | 'report' | 'file'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  type: 'text' | 'tool_call' | 'tool_result' | 'error'
  agentId?: string
  toolName?: string
  toolDesc?: string
  toolInput?: Record<string, unknown>
  artifactKind?: ArtifactKind
  timestamp: number
  streaming?: boolean
  thinking?: string
}

export interface Skill {
  id: string
  name: string
  description: string
}

export interface AgentInfo {
  id: string
  label: string
  description: string
  capabilities: string[]
  is_default: boolean
  execution_mode?: string
  risk_level?: string
  allowed_handoffs?: string[]
}

export interface ConversationItem {
  id: string
  title: string
  source?: string
  agent_id: string
  created_at: string | null
  updated_at: string | null
}

export interface ConversationHistoryMessage {
  id: string
  role: string
  content: string
  type: string
  agent_id: string | null
  tool_name: string | null
  tool_input: Record<string, unknown> | null
  thinking: string | null
  created_at: string | null
}

export interface MemoryNode {
  path: string
  name: string
  kind: 'file' | 'directory'
  children?: MemoryNode[]
  updated_at?: string | null
}

export interface MemoryDocument {
  path: string
  name: string
  content: string
  updated_at: string | null
}

export interface CloudContextCandidate {
  instance_id?: string | null
  instance_name?: string | null
  project_key?: string | null
  region?: string | null
  environment?: string | null
  credential_ref?: string | null
  credential_status?: string | null
  source?: string | null
  score?: number
}

export interface CloudContextResolution {
  matched: boolean
  ambiguous: boolean
  provider: string
  message: string
  instance_id?: string | null
  instance_name?: string | null
  project_key?: string | null
  region?: string | null
  environment?: string | null
  credential_ref?: string | null
  credential_status?: string | null
  source?: string | null
  candidates: CloudContextCandidate[]
}

export type McpTransport = 'http' | 'sse'
export type McpTestStatus = 'untested' | 'ok' | 'error'

export interface McpToolPreview {
  name: string
  description: string
}

export interface McpServer {
  id: string
  name: string
  transport: McpTransport
  url: string
  enabled: boolean
  agent_ids: string[]
  has_headers: boolean
  header_keys: string[]
  last_test_status: McpTestStatus
  last_tested_at: string | null
  last_error: string | null
  last_tools: McpToolPreview[]
  created_at: string | null
  updated_at: string | null
}

export interface McpServerPayload {
  name: string
  transport: McpTransport
  url: string
  enabled: boolean
  agent_ids: string[]
  headers?: Record<string, string>
}

export interface McpServerUpdatePayload extends McpServerPayload {
  replace_headers?: boolean
}

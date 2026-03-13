export type ArtifactKind = 'memory' | 'report' | 'file'

export interface ConversationAttachmentSnapshot {
  id: string
  conversation_id?: string
  original_name: string
  stored_name: string
  relative_path: string
  mime_type: string
  size_bytes: number
  created_at: string | null
}

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
  attachments?: ConversationAttachmentSnapshot[]
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

export interface AuthUser {
  id: string
  subject: string
  email: string | null
  display_name: string | null
  roles: string[]
  permissions: string[]
}

export interface AuthStatusResponse {
  auth_enabled: boolean
  authenticated: boolean
  oidc_login_enabled: boolean
  password_login_enabled: boolean
  login_methods: string[]
  user: AuthUser | null
  permissions: string[]
  available_permissions: string[]
  login_url: string
  logout_url: string
  redirect_to?: string
}

export interface ConversationItem {
  id: string
  title: string
  source?: string
  agent_id: string
  source_task_id?: string | null
  source_task_run_id?: string | null
  source_task_trigger_type?: 'manual' | 'scheduled' | null
  created_at: string | null
  updated_at: string | null
}

export interface InspectionTaskDraft {
  source_conversation_id: string | null
  name: string
  agent_id: string
  skill_id: string | null
  prompt_template: string
  target_payload: Record<string, unknown> | null
  schedule_type: 'cron'
  cron_expr: string
  enabled: boolean
}

export interface InspectionTask extends InspectionTaskDraft {
  id: string
  last_run_at: string | null
  next_run_at: string | null
  last_status: 'idle' | 'running' | 'succeeded' | 'failed'
  created_at: string | null
  updated_at: string | null
}

export interface InspectionTaskIntentAnalysis {
  intent_matched: boolean
  outcome: 'created' | 'error'
  cron_expr: string | null
  summary: string
  reason: string | null
}

export type InspectionTaskFromConversationMessageResult =
  | {
      status: 'created'
      task: InspectionTask
      intent_analysis?: InspectionTaskIntentAnalysis
    }
  | {
      status: 'not_task_creation'
    }
  | {
      status: 'error'
      message: string
      intent_analysis?: InspectionTaskIntentAnalysis
    }
  | {
      status: 'clarification_needed'
      message: string
      clarification_prompt: string
      intent_analysis?: InspectionTaskIntentAnalysis
    }

export interface InspectionTaskRun {
  id: string
  task_id: string
  trigger_type: 'manual' | 'scheduled'
  status: 'running' | 'succeeded' | 'failed'
  conversation_id: string | null
  started_at: string | null
  finished_at: string | null
  error_message: string | null
}

export interface TaskNotification {
  id: string
  task_id: string
  task_run_id: string
  conversation_id: string | null
  status: 'succeeded' | 'failed'
  title: string
  summary: string
  report_name: string | null
  report_path: string | null
  read_at: string | null
  created_at: string | null
}

export interface ConversationAttachment {
  id: string
  conversation_id: string
  original_name: string
  stored_name: string
  relative_path: string
  mime_type: string
  size_bytes: number
  created_at: string | null
}

export interface ConversationHistoryMessage {
  id: string
  role: string
  content: string
  type: string
  agent_id: string | null
  tool_name: string | null
  tool_input: Record<string, unknown> | null
  attachments_snapshot: ConversationAttachmentSnapshot[] | null
  thinking: string | null
  created_at: string | null
}

export type InspectionTaskRunConversationStreamEvent =
  | {
      type: 'history_start'
      run_id: string
      conversation_id: string
      agent_id: string
      title: string
      status: InspectionTaskRun['status']
    }
  | {
      type: 'message'
      message: ConversationHistoryMessage
    }
  | {
      type: 'history_done'
      run_id: string
      conversation_id: string
    }
  | {
      type: 'run_status'
      run_id: string
      conversation_id: string
      status: InspectionTaskRun['status']
      finished_at: string | null
      error_message: string | null
    }
  | {
      type: 'done'
      run_id: string
      conversation_id: string
      status: InspectionTaskRun['status']
      error_message?: string | null
    }
  | {
      type: 'error'
      content: string
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
  selection_required: boolean
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

export type McpTransport = 'http' | 'sse' | 'stdio'
export type McpTestStatus = 'untested' | 'ok' | 'error'

export interface McpToolPreview {
  name: string
  description: string
}

export interface McpServer {
  id: string
  name: string
  transport: McpTransport
  url: string | null
  command: string | null
  args: string[]
  env: Record<string, string> | null
  has_env: boolean
  env_keys: string[]
  enabled: boolean
  agent_ids: string[]
  has_headers: boolean
  header_keys: string[]
  last_test_status: McpTestStatus
  last_tested_at: string | null
  last_error: string | null
  last_tools: McpToolPreview[]
}

export interface McpConfigResponse {
  config_text: string
  servers: McpServer[]
}

export interface SendMessageOptions {
  attachments?: ConversationAttachmentSnapshot[]
}

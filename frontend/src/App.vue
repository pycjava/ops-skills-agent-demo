<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useAppChrome } from './composables/useAppChrome'
import { useChatComposer } from './composables/useChatComposer'
import ConversationAttachmentBar from './components/ConversationAttachmentBar.vue'
import ConversationList from './components/ConversationList.vue'
import ConversationTitleEditor from './components/ConversationTitleEditor.vue'
import McpPanel from './components/McpPanel.vue'
import MemoryPanel from './components/MemoryPanel.vue'
import MessageBubble from './components/MessageBubble.vue'
import MysqlInstanceSelectorDialog from './components/MysqlInstanceSelectorDialog.vue'
import SkillPanel from './components/SkillPanel.vue'
import { MAX_CONVERSATION_ATTACHMENTS } from './constants/attachments'
import { useChatStore, type CloudContextCandidate } from './stores/chat'
import { toAttachmentSnapshot } from './stores/chat/helpers'
import {
  buildMysqlSelectionSystemHint,
  isMysqlInspectionIntent,
} from './utils/mysqlInspection'

const chatStore = useChatStore()
const chatContainer = ref<HTMLElement | null>(null)
const titleRenameError = ref('')
const isTitleUpdating = ref(false)
const mysqlSelectionCandidates = ref<CloudContextCandidate[]>([])
const isMysqlSelectionOpen = ref(false)
const pendingMysqlMessage = ref<{
  displayContent: string
  sendContent: string
} | null>(null)
const quickPrompts: Array<{ label: string; prompt: string }> = []
const attachmentBarRef = ref<{ triggerFileSelect: () => void } | null>(null)

const hasMessages = computed(() => chatStore.messages.length > 0)
const agentLabels = computed(() =>
  Object.fromEntries(chatStore.agents.map((agent) => [agent.id, agent.label])),
)
const activeAgentLabel = computed(
  () =>
    chatStore.activeAgent?.label ||
    agentLabels.value[chatStore.activeAgentId] ||
    chatStore.activeAgentId,
)
const currentConversation = computed(
  () =>
    chatStore.conversations.find(
      (conversation) => conversation.id === chatStore.currentConversationId,
    ) ?? null,
)

const derivedConversationTitle = computed(() => {
  const firstUserMessage = chatStore.messages.find((message) => message.role === 'user')
  if (!firstUserMessage?.content) return '新对话'

  const title = firstUserMessage.content
    .replace(/\s+/g, ' ')
    .replace(/<system_hint>[\s\S]*?<\/system_hint>/g, '')
    .trim()

  if (!title) return '新对话'
  return title.length > 22 ? `${title.slice(0, 22)}…` : title
})

const currentConversationTitle = computed(
  () => currentConversation.value?.title || derivedConversationTitle.value,
)
const currentConversationSubtitle = computed(() =>
  hasMessages.value ? '对话由 AI 生成' : '',
)
const submittedAttachmentIds = computed(() => {
  const attachmentIds = new Set<string>()

  for (const message of chatStore.messages) {
    for (const attachment of message.attachments || []) {
      attachmentIds.add(attachment.id)
    }
  }

  return attachmentIds
})
const pendingConversationAttachments = computed(() =>
  chatStore.conversationAttachments.filter(
    (attachment) => !submittedAttachmentIds.value.has(attachment.id),
  ),
)
const pendingAttachmentSnapshots = computed(() =>
  pendingConversationAttachments.value.map((attachment) => toAttachmentSnapshot(attachment)),
)
const pendingSendOptions = computed(() =>
  pendingAttachmentSnapshots.value.length > 0
    ? { attachments: pendingAttachmentSnapshots.value }
    : undefined,
)

const {
  inputText,
  composerInput,
  showMentions,
  mentionIndex,
  filteredSkills,
  inputPlaceholder,
  clearInput,
  handleInput,
  handleKeyDown,
  handleSend,
  selectMention,
  sendQuickPrompt,
  resizeComposerInput,
} = useChatComposer({
  hasMessages,
  isConnected: computed(() => chatStore.isConnected),
  isLoading: computed(() => chatStore.isLoading),
  skills: computed(() => chatStore.skills),
  sendMessage: handleComposerSend,
})

const {
  showSidebar,
  isDark,
  showInspector,
  showAgentOverflowMenu,
  rightPanelTab,
  heroTitle,
  agentSelector,
  agentSelectorWrap,
  moreMeasureRef,
  visibleAgents,
  overflowAgents,
  setAgentMeasureRef,
  toggleAgentOverflowMenu,
  selectAgent,
  openInspector,
  closeInspector,
  handleOpenMemory,
  toggleTheme,
} = useAppChrome({
  agents: computed(() => chatStore.agents),
  setDraftAgent: chatStore.setDraftAgent,
  connect: chatStore.connect,
  fetchAgents: chatStore.fetchAgents,
  fetchConversations: chatStore.fetchConversations,
  fetchSkills: chatStore.fetchSkills,
  fetchMcpServers: chatStore.fetchMcpServers,
  fetchMemoryTree: chatStore.fetchMemoryTree,
  openMemoryDocument: chatStore.openMemoryDocument,
  resizeComposerInput,
})

void composerInput
void agentSelector
void agentSelectorWrap
void moreMeasureRef

const scrollTrigger = computed(() => {
  const length = chatStore.messages.length
  const lastContentLength = length > 0 ? chatStore.messages[length - 1]?.content?.length ?? 0 : 0
  return `${length}-${lastContentLength}`
})

watch(scrollTrigger, async () => {
  if (!hasMessages.value) return

  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
})

function closeMysqlSelection() {
  isMysqlSelectionOpen.value = false
  mysqlSelectionCandidates.value = []
  pendingMysqlMessage.value = null
}

function buildResolvedSendContent(sendContent: string, candidate?: CloudContextCandidate) {
  if (!candidate) return sendContent
  return `${sendContent}${buildMysqlSelectionSystemHint(candidate)}`
}

function sendWithPendingAttachments(displayContent: string, sendContent?: string) {
  if (pendingSendOptions.value) {
    chatStore.sendMessage(displayContent, sendContent, pendingSendOptions.value)
    return
  }

  chatStore.sendMessage(displayContent, sendContent)
}

async function handleComposerSend(displayContent: string, sendContent?: string) {
  const normalizedDisplayContent = displayContent.trim()
  const normalizedSendContent = (sendContent || displayContent).trim()

  if (
    chatStore.activeAgentId !== 'dba' ||
    !isMysqlInspectionIntent(normalizedDisplayContent)
  ) {
    sendWithPendingAttachments(normalizedDisplayContent, normalizedSendContent)
    return true
  }

  try {
    const resolution = await chatStore.resolveCloudRequestContext(normalizedDisplayContent)

    if (resolution.selection_required) {
      pendingMysqlMessage.value = {
        displayContent: normalizedDisplayContent,
        sendContent: normalizedSendContent,
      }
      mysqlSelectionCandidates.value = resolution.candidates
      isMysqlSelectionOpen.value = true
      return false
    }

    const selectedCandidate =
      resolution.matched && resolution.candidates.length > 0
        ? resolution.candidates[0]
        : undefined

    sendWithPendingAttachments(
      normalizedDisplayContent,
      buildResolvedSendContent(normalizedSendContent, selectedCandidate),
    )
    return true
  } catch (error) {
    console.warn('解析 MySQL 巡检候选失败，回退为直接发送:', error)
    sendWithPendingAttachments(normalizedDisplayContent, normalizedSendContent)
    return true
  }
}

function confirmMysqlSelection(candidate: CloudContextCandidate) {
  if (!pendingMysqlMessage.value) return

  sendWithPendingAttachments(
    pendingMysqlMessage.value.displayContent,
    buildResolvedSendContent(pendingMysqlMessage.value.sendContent, candidate),
  )
  clearInput()
  closeMysqlSelection()
}

function triggerAttachmentSelect() {
  if (!chatStore.isConnected || chatStore.isAttachmentUploading || chatStore.isLoading) {
    return
  }

  attachmentBarRef.value?.triggerFileSelect()
}

function buildAttachmentLimitError(remainingSlots: number) {
  if (remainingSlots <= 0) {
    return `当前会话最多 ${MAX_CONVERSATION_ATTACHMENTS} 个附件`
  }

  return `当前会话最多 ${MAX_CONVERSATION_ATTACHMENTS} 个附件，还可上传 ${remainingSlots} 个`
}

async function handleAttachmentUpload(files: File[]) {
  chatStore.attachmentError = null
  const remainingSlots =
    MAX_CONVERSATION_ATTACHMENTS - chatStore.conversationAttachments.length

  if (remainingSlots <= 0 || files.length > remainingSlots) {
    chatStore.attachmentError = buildAttachmentLimitError(remainingSlots)
    return
  }

  let failedCount = 0

  for (const file of files) {
    const uploaded = await chatStore.uploadConversationAttachment(file)
    if (!uploaded) {
      failedCount += 1
    }
  }

  if (failedCount > 0) {
    chatStore.attachmentError = `${files.length} 个文件中 ${failedCount} 个上传失败`
  }
}

async function handleAttachmentDelete(attachmentId: string) {
  await chatStore.deleteConversationAttachment(attachmentId)
}

async function handleConversationTitleSave(title: string) {
  if (!chatStore.currentConversationId) return

  titleRenameError.value = ''
  isTitleUpdating.value = true

  try {
    await chatStore.updateConversationTitle(chatStore.currentConversationId, title)
  } catch (error) {
    titleRenameError.value = error instanceof Error ? error.message : '修改标题失败'
  } finally {
    isTitleUpdating.value = false
  }
}
</script>

<template>
  <div class="app-shell">
    <aside v-if="showSidebar" class="sidebar-frame">
      <div class="sidebar-brand">
        <div class="brand-mark">C</div>
        <div class="brand-copy">
          <span class="brand-name">Claude Agent</span>
          <span class="brand-subtitle">智能对话工作台</span>
        </div>
        <button class="icon-btn subtle" title="收起侧栏" @click="showSidebar = false">
          ‹
        </button>
      </div>

      <ConversationList
        :conversations="chatStore.conversations"
        :current-id="chatStore.currentConversationId"
        :agent-labels="agentLabels"
        @select="chatStore.switchConversation"
        @create="chatStore.createConversation"
        @delete="chatStore.deleteConversation"
        @search="chatStore.fetchConversations"
      />
    </aside>

    <main class="workspace" :class="{ 'workspace-chat': hasMessages }">
      <div class="workspace-toolbar">
        <div class="toolbar-left">
          <button
            v-if="!showSidebar"
            class="icon-btn"
            title="显示侧栏"
            @click="showSidebar = true"
          >
            ☰
          </button>
        </div>

        <div class="toolbar-right">
          <button
            class="icon-btn"
            :disabled="chatStore.messages.length === 0"
            title="清空当前对话"
            @click="chatStore.clearChat"
          >
            ⌫
          </button>
          <button
            class="icon-btn"
            :title="isDark ? '切换浅色模式' : '切换深色模式'"
            @click="toggleTheme"
          >
            {{ isDark ? '☀️' : '🌙' }}
          </button>
          <button class="icon-btn" title="打开右侧面板" @click="openInspector('skills')">
            ☷
          </button>
        </div>
      </div>

      <section v-if="!hasMessages" class="empty-state">
        <div class="hero-panel">
          <h1 class="hero-title">{{ heroTitle }}</h1>

          <div class="composer composer-home">
            <div v-if="showMentions && filteredSkills.length > 0" class="mentions-popup">
              <div
                v-for="(skill, index) in filteredSkills"
                :key="skill.id"
                class="mention-item"
                :class="{ active: index === mentionIndex }"
                @click="selectMention(skill.id)"
                @mouseenter="mentionIndex = index"
              >
                <span class="mention-name">@{{ skill.id }}</span>
                <span class="mention-desc">{{ skill.description }}</span>
              </div>
            </div>

            <ConversationAttachmentBar
              ref="attachmentBarRef"
              :attachments="pendingConversationAttachments"
              :is-uploading="chatStore.isAttachmentUploading"
              :error="chatStore.attachmentError"
              :disabled="!chatStore.isConnected"
              @upload="handleAttachmentUpload"
              @delete="handleAttachmentDelete"
            />

            <textarea
              ref="composerInput"
              v-model="inputText"
              class="composer-input composer-input-home"
              :placeholder="inputPlaceholder"
              rows="1"
              :disabled="!chatStore.isConnected"
              @keydown="handleKeyDown"
              @input="handleInput"
            />

            <div class="composer-footer">
              <div class="composer-hints">
                <span class="hint-pill">@ 指定技能</span>
                <span class="hint-pill">Enter 发送</span>
                <span class="hint-pill">Shift + Enter 换行</span>
              </div>

              <div class="composer-actions">
                <button
                  type="button"
                  class="composer-upload-btn"
                  data-testid="composer-upload-trigger"
                  title="上传附件"
                  aria-label="上传附件"
                  :disabled="!chatStore.isConnected || chatStore.isAttachmentUploading || chatStore.isLoading"
                  @click="triggerAttachmentSelect"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path
                      d="M8.5 12.5 15 6a3.5 3.5 0 1 1 5 5l-9 9a5.5 5.5 0 0 1-7.8-7.8l8.7-8.7"
                      fill="none"
                      stroke="currentColor"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="1.8"
                    />
                  </svg>
                </button>

                <button
                  class="send-btn"
                  :disabled="!inputText.trim() || !chatStore.isConnected"
                  @click="handleSend"
                >
                  →
                </button>
              </div>
            </div>
          </div>

          <div v-if="chatStore.agents.length > 0" ref="agentSelectorWrap" class="agent-selector">
            <div ref="agentSelector" class="agent-selector-list">
              <button
                v-for="agent in visibleAgents"
                :key="agent.id"
                class="agent-selector-item"
                :class="{ active: agent.id === chatStore.draftAgentId }"
                @click="selectAgent(agent.id)"
              >
                <span class="agent-selector-name">{{ agent.label }}</span>
                <span class="agent-selector-id">{{ agent.id }}</span>
              </button>

              <div v-if="overflowAgents.length > 0" class="agent-overflow">
                <button
                  class="agent-selector-item agent-selector-more"
                  :class="{ active: showAgentOverflowMenu }"
                  @click.stop="toggleAgentOverflowMenu"
                >
                  <span class="agent-selector-name">更多</span>
                  <span class="agent-selector-arrow">▾</span>
                </button>

                <div v-if="showAgentOverflowMenu" class="agent-overflow-menu">
                  <button
                    v-for="agent in overflowAgents"
                    :key="agent.id"
                    class="agent-overflow-item"
                    :class="{ active: agent.id === chatStore.draftAgentId }"
                    @click="selectAgent(agent.id)"
                  >
                    <span class="agent-selector-name">{{ agent.label }}</span>
                    <span class="agent-selector-id">{{ agent.id }}</span>
                  </button>
                </div>
              </div>
            </div>

            <div class="agent-measure" aria-hidden="true">
              <button
                v-for="(agent, index) in chatStore.agents"
                :key="`${agent.id}-measure`"
                :ref="(element) => setAgentMeasureRef(element, index)"
                class="agent-selector-item agent-selector-measure"
                tabindex="-1"
              >
                <span class="agent-selector-name">{{ agent.label }}</span>
                <span class="agent-selector-id">{{ agent.id }}</span>
              </button>
              <button
                ref="moreMeasureRef"
                class="agent-selector-item agent-selector-more agent-selector-measure"
                tabindex="-1"
              >
                <span class="agent-selector-name">更多</span>
                <span class="agent-selector-arrow">▾</span>
              </button>
            </div>
          </div>

          <div v-if="quickPrompts.length > 0" class="quick-actions">
            <button
              v-for="item in quickPrompts"
              :key="item.label"
              class="quick-action"
              @click="sendQuickPrompt(item.prompt)"
            >
              {{ item.label }}
            </button>
          </div>
        </div>
      </section>

      <section v-else class="chat-state">
        <div class="chat-header">
          <div class="chat-meta">
            <span class="chat-kicker">{{ currentConversationSubtitle }}</span>
            <span class="agent-chip">{{ activeAgentLabel }}</span>
          </div>
          <ConversationTitleEditor
            v-if="chatStore.currentConversationId"
            :title="currentConversationTitle"
            :error="titleRenameError"
            :saving="isTitleUpdating"
            @save="handleConversationTitleSave"
            @cancel="titleRenameError = ''"
          />
          <h2 v-else class="chat-title">{{ currentConversationTitle }}</h2>
        </div>

        <div ref="chatContainer" class="chat-scroll">
          <div class="chat-column">
            <MessageBubble
              v-for="message in chatStore.messages"
              :key="message.id"
              :message="message"
              @open-memory="handleOpenMemory"
              @delete-attachment="handleAttachmentDelete"
            />

            <div v-if="chatStore.isLoading" class="typing-indicator">
              <span class="typing-dot"></span>
              <span>正在生成回复…</span>
            </div>
          </div>
        </div>

        <div class="composer-dock">
          <div class="composer composer-chat">
            <div v-if="showMentions && filteredSkills.length > 0" class="mentions-popup">
              <div
                v-for="(skill, index) in filteredSkills"
                :key="skill.id"
                class="mention-item"
                :class="{ active: index === mentionIndex }"
                @click="selectMention(skill.id)"
                @mouseenter="mentionIndex = index"
              >
                <span class="mention-name">@{{ skill.id }}</span>
                <span class="mention-desc">{{ skill.description }}</span>
              </div>
            </div>

            <ConversationAttachmentBar
              ref="attachmentBarRef"
              :attachments="pendingConversationAttachments"
              :is-uploading="chatStore.isAttachmentUploading"
              :error="chatStore.attachmentError"
              :disabled="!chatStore.isConnected"
              @upload="handleAttachmentUpload"
              @delete="handleAttachmentDelete"
            />

            <textarea
              ref="composerInput"
              v-model="inputText"
              class="composer-input composer-input-chat"
              :placeholder="inputPlaceholder"
              rows="1"
              :disabled="!chatStore.isConnected"
              @keydown="handleKeyDown"
              @input="handleInput"
            />

            <div class="composer-footer">
              <div class="composer-hints">
                <span class="hint-pill">@ 指定技能</span>
                <span class="hint-pill">Enter 发送</span>
              </div>

              <div class="composer-actions">
                <button
                  type="button"
                  class="composer-upload-btn"
                  data-testid="composer-upload-trigger"
                  title="上传附件"
                  aria-label="上传附件"
                  :disabled="!chatStore.isConnected || chatStore.isAttachmentUploading || chatStore.isLoading"
                  @click="triggerAttachmentSelect"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path
                      d="M8.5 12.5 15 6a3.5 3.5 0 1 1 5 5l-9 9a5.5 5.5 0 0 1-7.8-7.8l8.7-8.7"
                      fill="none"
                      stroke="currentColor"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="1.8"
                    />
                  </svg>
                </button>

                <button
                  v-if="chatStore.isLoading"
                  class="send-btn stop-btn"
                  @click="chatStore.abortAgent()"
                >
                  ■
                </button>
                <button
                  v-else
                  class="send-btn"
                  :disabled="!inputText.trim() || !chatStore.isConnected"
                  @click="handleSend"
                >
                  →
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <MysqlInstanceSelectorDialog
        :visible="isMysqlSelectionOpen"
        :candidates="mysqlSelectionCandidates"
        :pending-message="pendingMysqlMessage?.displayContent || ''"
        @select="confirmMysqlSelection"
        @cancel="closeMysqlSelection"
      />

      <transition name="drawer-fade">
        <div v-if="showInspector" class="inspector-overlay" @click.self="closeInspector">
          <aside class="inspector-drawer">
            <div class="inspector-head">
              <div class="inspector-tabs">
                <button
                  class="inspector-tab"
                  :class="{ active: rightPanelTab === 'skills' }"
                  @click="rightPanelTab = 'skills'"
                >
                  Skills
                </button>
                <button
                  class="inspector-tab"
                  :class="{ active: rightPanelTab === 'mcp' }"
                  @click="rightPanelTab = 'mcp'"
                >
                  MCP
                </button>
                <button
                  class="inspector-tab"
                  :class="{ active: rightPanelTab === 'memory' }"
                  @click="rightPanelTab = 'memory'"
                >
                  Memory
                </button>
              </div>

              <button class="icon-btn subtle" title="关闭面板" @click="closeInspector">
                ✕
              </button>
            </div>

            <div class="inspector-body">
              <SkillPanel v-if="rightPanelTab === 'skills'" :skills="chatStore.skills" />
              <McpPanel v-else-if="rightPanelTab === 'mcp'" />
              <MemoryPanel
                v-else
                :nodes="chatStore.memoryTree"
                :selected-path="chatStore.selectedMemoryPath"
                :document="chatStore.memoryContent"
                :is-loading="chatStore.isMemoryLoading"
                :error="chatStore.memoryError"
                @select="chatStore.fetchMemoryContent"
                @delete="chatStore.deleteMemoryFile"
                @refresh="chatStore.fetchMemoryTree(true)"
              />
            </div>
          </aside>
        </div>
      </transition>
    </main>
  </div>
</template>

<style>
:root,
[data-theme='light'] {
  --bg: #f7f4ed;
  --bg-soft: #f0ece2;
  --sidebar-bg: #f3efe6;
  --card: rgba(255, 255, 255, 0.76);
  --card-strong: #fbfaf6;
  --card-muted: #ece6d9;
  --hover: #ebe4d7;
  --border: rgba(137, 121, 92, 0.18);
  --border-strong: rgba(122, 108, 82, 0.28);
  --text: #5d5648;
  --text-strong: #1f1a14;
  --text-muted: #9a907d;
  --text-soft: #b6aa95;
  --selection: rgba(126, 112, 83, 0.1);
  --bubble-user: #ede8dd;
  --success: #71936f;
  --warning: #b38a59;
  --danger: #c86f64;
  --accent: #8b73ff;
  --shadow-soft: 0 20px 50px rgba(86, 73, 51, 0.08);
  --shadow-card: 0 12px 32px rgba(86, 73, 51, 0.08);
}

[data-theme='dark'] {
  --bg: #151618;
  --bg-soft: #1d1f23;
  --sidebar-bg: #181a1f;
  --card: rgba(29, 31, 35, 0.92);
  --card-strong: #20242b;
  --card-muted: #23262d;
  --hover: #262a31;
  --border: rgba(255, 255, 255, 0.08);
  --border-strong: rgba(255, 255, 255, 0.15);
  --text: #d0d4db;
  --text-strong: #f5f7fa;
  --text-muted: #8f97a3;
  --text-soft: #6f7782;
  --selection: rgba(255, 255, 255, 0.06);
  --bubble-user: #2a2e35;
  --success: #86b381;
  --warning: #d4a66b;
  --danger: #d97d73;
  --accent: #9e8eff;
  --shadow-soft: 0 24px 60px rgba(0, 0, 0, 0.32);
  --shadow-card: 0 16px 36px rgba(0, 0, 0, 0.28);
}

* {
  box-sizing: border-box;
}

html,
body,
#app {
  width: 100%;
  height: 100%;
  margin: 0;
}

body {
  background: var(--bg);
  color: var(--text);
  font-family:
    Inter,
    'PingFang SC',
    'Hiragino Sans GB',
    'Microsoft YaHei',
    'Helvetica Neue',
    Arial,
    sans-serif;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

button,
textarea,
input {
  font: inherit;
}

.app-shell {
  display: flex;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: var(--bg);
}

.sidebar-frame {
  width: 272px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 18px 12px;
}

.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #ff58c2 0%, var(--accent) 100%);
  box-shadow: 0 10px 20px rgba(139, 115, 255, 0.24);
}

.brand-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.brand-name {
  color: var(--text-strong);
  font-size: 16px;
  font-weight: 700;
}

.brand-subtitle {
  color: var(--text-muted);
  font-size: 12px;
}

.workspace {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(circle at top center, rgba(255, 255, 255, 0.5), transparent 34%),
    var(--bg);
}

.workspace-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px 0;
  position: relative;
  z-index: 2;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.icon-btn {
  width: 40px;
  height: 40px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.58);
  color: var(--text);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    transform 0.15s ease,
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease;
  backdrop-filter: blur(8px);
}

[data-theme='dark'] .icon-btn {
  background: rgba(32, 36, 43, 0.72);
}

.icon-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  background: var(--card-strong);
  color: var(--text-strong);
}

.icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.icon-btn.subtle {
  width: 34px;
  height: 34px;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 48px 48px;
}

.hero-panel {
  width: min(100%, 920px);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 28px;
}

.hero-title {
  margin: 0;
  color: var(--text-strong);
  font-family:
    'Noto Serif SC',
    'Songti SC',
    'STSong',
    serif;
  font-size: clamp(28px, 4.0vw, 50px);
  font-weight: 500;
  letter-spacing: 0.02em;
  text-align: center;
}

.agent-selector {
  width: min(100%, 820px);
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: relative;
}

.agent-selector-list {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex-wrap: nowrap;
  min-width: 0;
  overflow: hidden;
}

.agent-selector-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--card);
  color: var(--text);
  cursor: pointer;
  transition:
    transform 0.15s ease,
    border-color 0.15s ease,
    background 0.15s ease;
  white-space: nowrap;
  flex-shrink: 0;
}

.agent-selector-item:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  background: var(--card-strong);
}

.agent-selector-item.active {
  border-color: rgba(139, 115, 255, 0.35);
  background: rgba(139, 115, 255, 0.12);
  color: var(--text-strong);
}

.agent-selector-more {
  gap: 6px;
}

.agent-selector-arrow {
  font-size: 11px;
  color: var(--text-muted);
}

.agent-overflow {
  position: relative;
  flex-shrink: 0;
}

.agent-overflow-menu {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  min-width: 180px;
  max-width: min(320px, 80vw);
  max-height: 260px;
  overflow-y: auto;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--card-strong);
  box-shadow: var(--shadow-card);
  z-index: 12;
}

.agent-overflow-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  text-align: left;
}

.agent-overflow-item:hover {
  background: var(--hover);
}

.agent-overflow-item.active {
  background: rgba(139, 115, 255, 0.12);
  color: var(--text-strong);
}

.agent-measure {
  position: absolute;
  left: 0;
  top: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  visibility: hidden;
  pointer-events: none;
  white-space: nowrap;
  height: 0;
  overflow: hidden;
}

.agent-selector-measure {
  transform: none !important;
}

.agent-selector-name {
  font-size: 13px;
  font-weight: 600;
}

.agent-selector-id {
  color: var(--text-muted);
  font-size: 11px;
}

.composer {
  position: relative;
  width: 100%;
  border: 1px solid var(--border-strong);
  border-radius: 28px;
  background: var(--card);
  box-shadow: var(--shadow-soft);
  backdrop-filter: blur(12px);
}

.composer-home {
  max-width: 820px;
  padding: 20px 20px 18px;
}

.composer-chat {
  max-width: 860px;
  margin: 0 auto;
  padding: 16px 18px 14px;
  border-radius: 24px;
  box-shadow: var(--shadow-card);
}

.composer:focus-within {
  border-color: rgba(139, 115, 255, 0.28);
  box-shadow:
    var(--shadow-card),
    0 0 0 4px rgba(139, 115, 255, 0.08);
}

.composer-input {
  width: 100%;
  resize: none;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-strong);
  line-height: 1.75;
  overflow-y: hidden;
  display: block;
}

.composer-input-home {
  min-height: 48px;
  max-height: 320px;
  font-size: 18px;
}

.composer-input-chat {
  min-height: 36px;
  max-height: 220px;
  font-size: 16px;
}

.composer-input::placeholder {
  color: var(--text-soft);
}

.composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 14px;
}

.composer-hints {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.composer-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.hint-pill {
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--bg-soft);
  color: var(--text-muted);
  font-size: 12px;
}

.composer-upload-btn,
.send-btn {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 999px;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    opacity 0.15s ease,
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.composer-upload-btn {
  border: 1px solid var(--border);
  background: var(--card-strong);
  color: var(--text-strong);
}

.composer-upload-btn svg {
  width: 18px;
  height: 18px;
}

.send-btn {
  border: none;
  background: var(--text-strong);
  color: var(--card-strong);
  font-size: 18px;
}

.composer-upload-btn:hover:not(:disabled),
.send-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.composer-upload-btn:hover:not(:disabled) {
  border-color: var(--border-strong);
  background: var(--hover);
}

.composer-upload-btn:disabled,
.send-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.stop-btn {
  background: var(--danger);
  color: #fff;
}

.quick-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 12px;
}

.quick-action {
  padding: 12px 18px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease;
}

.quick-action:hover {
  background: var(--card-strong);
  border-color: var(--border-strong);
  color: var(--text-strong);
}

.chat-state {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 8px 28px 24px;
}

.chat-header {
  width: min(100%, 880px);
  margin: 0 auto;
  padding: 2px 8px 10px;
}

.chat-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.chat-kicker {
  display: inline-flex;
  color: var(--text-muted);
  font-size: 12px;
}

.agent-chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(139, 115, 255, 0.12);
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
}

.chat-title {
  margin: 0;
  color: var(--text-strong);
  font-size: clamp(24px, 3vw, 34px);
  font-weight: 700;
}

.chat-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 0 24px;
}

.chat-scroll::-webkit-scrollbar {
  width: 8px;
}

.chat-scroll::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 999px;
}

.chat-column {
  width: min(100%, 880px);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 26px;
}

.typing-indicator {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 0 6px 8px;
  color: var(--text-muted);
  font-size: 14px;
}

.typing-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--accent);
  box-shadow:
    12px 0 0 rgba(139, 115, 255, 0.5),
    24px 0 0 rgba(139, 115, 255, 0.25);
  animation: pulse-dot 1s ease-in-out infinite;
}

@keyframes pulse-dot {
  50% {
    opacity: 0.45;
  }
}

.composer-dock {
  padding-top: 12px;
}

.mentions-popup {
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: calc(100% + 12px);
  max-height: 220px;
  overflow-y: auto;
  padding: 6px;
  border: 1px solid var(--border-strong);
  border-radius: 18px;
  background: var(--card-strong);
  box-shadow: var(--shadow-card);
  z-index: 8;
}

.mention-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 12px;
  cursor: pointer;
}

.mention-item:hover,
.mention-item.active {
  background: var(--hover);
}

.mention-name {
  color: var(--text-strong);
  font-size: 13px;
  font-weight: 600;
}

.mention-desc {
  color: var(--text-muted);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.inspector-overlay {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  justify-content: flex-end;
  padding: 16px;
  background: rgba(31, 26, 20, 0.12);
}

[data-theme='dark'] .inspector-overlay {
  background: rgba(0, 0, 0, 0.26);
}

.inspector-drawer {
  width: min(420px, 100%);
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 24px;
  background: var(--card-strong);
  box-shadow: var(--shadow-soft);
}

.inspector-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border);
}

.inspector-tabs {
  display: inline-flex;
  gap: 8px;
  padding: 4px;
  border-radius: 999px;
  background: var(--bg-soft);
}

.inspector-tab {
  padding: 8px 14px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}

.inspector-tab.active {
  background: var(--card-strong);
  color: var(--text-strong);
  box-shadow: 0 4px 12px rgba(86, 73, 51, 0.08);
}

.inspector-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.drawer-fade-enter-active,
.drawer-fade-leave-active {
  transition: opacity 0.2s ease;
}

.drawer-fade-enter-active .inspector-drawer,
.drawer-fade-leave-active .inspector-drawer {
  transition: transform 0.2s ease;
}

.drawer-fade-enter-from,
.drawer-fade-leave-to {
  opacity: 0;
}

.drawer-fade-enter-from .inspector-drawer,
.drawer-fade-leave-to .inspector-drawer {
  transform: translateX(18px);
}

@media (max-width: 1100px) {
  .sidebar-frame {
    width: 248px;
  }

  .hero-title {
    font-size: clamp(28px, 3.6vw, 40px);
  }
}

@media (max-width: 820px) {
  .app-shell {
    position: relative;
  }

  .sidebar-frame {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 15;
    box-shadow: var(--shadow-soft);
  }

  .workspace-toolbar,
  .chat-state,
  .empty-state {
    padding-left: 18px;
    padding-right: 18px;
  }

  .composer-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .composer-actions {
    align-self: flex-end;
  }
}
</style>


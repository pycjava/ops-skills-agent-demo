<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { MemoryDocument, MemoryNode } from '../stores/chat'
import MemoryTreeNode from './MemoryTreeNode.vue'

const props = defineProps<{
  nodes: MemoryNode[]
  selectedPath: string | null
  document: MemoryDocument | null
  isLoading: boolean
  error: string | null
}>()

const emit = defineEmits<{
  (e: 'select', path: string): void
  (e: 'refresh'): void
  (e: 'delete', path: string): void
}>()

const expandedPaths = ref<string[]>([])
const showDeleteConfirm = ref(false)

const isEmpty = computed(() => props.nodes.length === 0)
const canDeleteDocument = computed(() => Boolean(props.document?.path))
const isDocumentLoading = computed(() => {
  if (!props.selectedPath || !props.isLoading) return false
  return props.document?.path !== props.selectedPath
})

function collectTopLevelDirectories(nodes: MemoryNode[]): string[] {
  return nodes.filter(node => node.kind === 'directory').map(node => node.path)
}

function expandAncestors(path: string | null) {
  if (!path) return

  const segments = path.split('/').filter(Boolean)
  let current = ''
  for (let index = 0; index < segments.length - 1; index += 1) {
    current += `/${segments[index]}`
    const directoryPath = `${current}/`
    if (!expandedPaths.value.includes(directoryPath)) {
      expandedPaths.value.push(directoryPath)
    }
  }
}

function togglePath(path: string) {
  if (expandedPaths.value.includes(path)) {
    expandedPaths.value = expandedPaths.value.filter(item => item !== path)
    return
  }

  expandedPaths.value = [...expandedPaths.value, path]
}

function formatTime(iso: string | null | undefined) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function requestDelete() {
  if (!props.document?.path || props.isLoading) return
  showDeleteConfirm.value = true
}

function cancelDelete() {
  showDeleteConfirm.value = false
}

function handleDelete() {
  const path = props.document?.path
  if (!path || props.isLoading) return
  showDeleteConfirm.value = false
  emit('delete', path)
}

watch(
  () => props.nodes,
  (nodes) => {
    expandedPaths.value = collectTopLevelDirectories(nodes)
    expandAncestors(props.selectedPath)
  },
  { immediate: true, deep: true },
)

watch(
  () => props.selectedPath,
  (path) => {
    showDeleteConfirm.value = false
    expandAncestors(path)
  },
  { immediate: true },
)

watch(
  () => props.document?.path,
  () => {
    showDeleteConfirm.value = false
  },
)
</script>

<template>
  <div class="memory-panel">
    <div class="memory-note">
      <span class="memory-note-title">长期记忆</span>
      <span class="memory-note-text">这里展示跨会话复用的信息，不是左侧的聊天历史。</span>
      <span v-if="error" class="memory-note-error">{{ error }}</span>
    </div>

    <div class="memory-split">
      <section class="memory-section memory-tree">
        <div class="memory-section-head">
          <span class="memory-section-title">记忆目录</span>
          <button class="memory-refresh" @click="emit('refresh')">刷新</button>
        </div>

        <div v-if="isLoading && isEmpty" class="memory-empty">
          <span class="dim">正在加载记忆...</span>
        </div>
        <div v-else-if="isEmpty" class="memory-empty">
          <span class="dim">还没有可展示的长期记忆</span>
        </div>
        <div v-else class="memory-tree-list">
          <MemoryTreeNode
            v-for="node in nodes"
            :key="node.path"
            :node="node"
            :selected-path="selectedPath"
            :expanded-paths="expandedPaths"
            @select="emit('select', $event)"
            @toggle="togglePath"
          />
        </div>
      </section>

      <section class="memory-section memory-preview">
        <div class="memory-section-head">
          <div class="memory-preview-meta">
            <span class="memory-section-title">内容预览</span>
            <span v-if="document?.updated_at" class="memory-updated">
              {{ formatTime(document.updated_at) }}
            </span>
          </div>
          <div class="memory-head-actions">
            <button
              v-if="canDeleteDocument"
              class="memory-delete"
              :disabled="isLoading"
              @click="requestDelete"
            >
              删除
            </button>
          </div>
        </div>

        <transition name="memory-confirm-fade">
          <div v-if="showDeleteConfirm && document" class="memory-confirm">
            <div class="memory-confirm-copy">
              <div class="memory-confirm-title">确认删除当前记忆文件？</div>
              <div class="memory-confirm-text">
                删除后将无法恢复，当前文件会从记忆列表中移除。
              </div>
              <div class="memory-confirm-file">{{ document.name }}</div>
            </div>
            <div class="memory-confirm-actions">
              <button
                class="memory-confirm-btn memory-confirm-cancel"
                :disabled="isLoading"
                @click="cancelDelete"
              >
                取消
              </button>
              <button
                class="memory-confirm-btn memory-confirm-submit"
                :disabled="isLoading"
                @click="handleDelete"
              >
                确认删除
              </button>
            </div>
          </div>
        </transition>

        <div v-if="error && !document" class="memory-empty">
          <span class="dim">{{ error }}</span>
        </div>
        <div v-else-if="!selectedPath" class="memory-empty">
          <span class="dim">从上方选择一个记忆文件查看详情</span>
        </div>
        <div v-else-if="isDocumentLoading" class="memory-empty">
          <span class="dim">正在读取记忆内容...</span>
        </div>
        <div v-else-if="document" class="memory-content">
          <div class="memory-document-name">{{ document.name }}</div>
          <pre class="memory-document-body">{{ document.content || '（空文件）' }}</pre>
        </div>
        <div v-else class="memory-empty">
          <span class="dim">暂时无法读取该记忆内容</span>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.memory-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px;
  height: 100%;
  min-height: 0;
}

.memory-note {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-input);
}

.memory-note-title {
  color: var(--cyan);
  font-size: 12px;
  font-weight: 600;
}

.memory-note-text {
  color: var(--text-dim);
  font-size: 11px;
  line-height: 1.5;
}

.memory-note-error {
  color: var(--red);
  font-size: 11px;
}

.memory-split {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-rows: minmax(160px, 42%) minmax(0, 1fr);
  gap: 10px;
}

.memory-section {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-panel);
}

.memory-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
}

.memory-section-title {
  color: var(--text-bright);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.memory-refresh {
  border: 1px solid var(--border);
  border-radius: 4px;
  background: transparent;
  color: var(--text-dim);
  font-size: 11px;
  padding: 4px 8px;
  cursor: pointer;
}

.memory-refresh:hover {
  color: var(--text);
  border-color: var(--text-dim);
}

.memory-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.memory-delete {
  border: 1px solid var(--border);
  border-radius: 999px;
  background: transparent;
  color: var(--danger);
  font-size: 11px;
  font-weight: 600;
  padding: 6px 12px;
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    transform 0.15s ease,
    opacity 0.15s ease;
}

.memory-delete:hover:not(:disabled) {
  background: rgba(200, 111, 100, 0.12);
  border-color: var(--danger);
  transform: translateY(-1px);
}

.memory-delete:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.memory-confirm {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 12px 12px 0;
  padding: 14px;
  border: 1px solid rgba(200, 111, 100, 0.2);
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(200, 111, 100, 0.08), rgba(200, 111, 100, 0.03));
  box-shadow: 0 12px 24px rgba(31, 26, 20, 0.08);
}

.memory-confirm-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.memory-confirm-title {
  color: var(--text-bright);
  font-size: 13px;
  font-weight: 600;
}

.memory-confirm-text {
  color: var(--text-dim);
  font-size: 12px;
  line-height: 1.6;
}

.memory-confirm-file {
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.28);
  color: var(--danger);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.memory-confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.memory-confirm-btn {
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    opacity 0.15s ease;
}

.memory-confirm-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.memory-confirm-cancel {
  background: transparent;
  color: var(--text-dim);
}

.memory-confirm-cancel:hover:not(:disabled) {
  background: var(--bg-input);
  color: var(--text);
}

.memory-confirm-submit {
  border-color: var(--danger);
  background: var(--danger);
  color: #fff;
}

.memory-confirm-submit:hover:not(:disabled) {
  filter: brightness(1.03);
}

.memory-confirm-fade-enter-active,
.memory-confirm-fade-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.memory-confirm-fade-enter-from,
.memory-confirm-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.memory-tree-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.memory-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  text-align: center;
}

.dim {
  color: var(--text-dim);
  font-size: 12px;
  line-height: 1.6;
}

.memory-preview-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.memory-updated {
  color: var(--text-dim);
  font-size: 10px;
}

.memory-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.memory-document-name {
  color: var(--cyan);
  font-size: 12px;
  font-weight: 600;
  padding: 10px 12px 0;
}

.memory-document-body {
  flex: 1;
  min-height: 0;
  margin: 0;
  padding: 10px 12px 12px;
  overflow: auto;
  color: var(--text-bright);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>

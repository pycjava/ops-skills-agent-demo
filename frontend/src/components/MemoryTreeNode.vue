<script setup lang="ts">
import { computed } from 'vue'
import type { MemoryNode } from '../stores/chat'

defineOptions({ name: 'MemoryTreeNode' })

const props = withDefaults(defineProps<{
  node: MemoryNode
  level?: number
  selectedPath: string | null
  expandedPaths: string[]
}>(), {
  level: 0,
})

const emit = defineEmits<{
  (e: 'select', path: string): void
  (e: 'toggle', path: string): void
  (e: 'request-delete', path: string): void
}>()

const isDirectory = computed(() => props.node.kind === 'directory')
const isExpanded = computed(() => props.expandedPaths.includes(props.node.path))
const isActiveBranch = computed(() => {
  if (!props.selectedPath) return false
  return props.selectedPath === props.node.path || props.selectedPath.startsWith(props.node.path)
})
const showDeleteAction = computed(() => !isDirectory.value)

const friendlyLabels: Record<string, string> = {
  'instructions.txt': '系统指令',
  'hosts.txt': '主机清单',
  'user_preferences.txt': '用户偏好',
  ops: '运维记录',
}

const friendlyLabel = computed(() => friendlyLabels[props.node.name] || '')

function handleClick() {
  if (isDirectory.value) {
    emit('toggle', props.node.path)
    return
  }

  emit('select', props.node.path)
}
</script>

<template>
  <div class="memory-node">
    <div
      class="memory-row-shell"
      :class="{
        'memory-row-dir': isDirectory,
        'memory-row-file': !isDirectory,
        active: selectedPath === node.path,
        'active-branch': isDirectory && isActiveBranch,
      }"
    >
      <button
        class="memory-row"
        :style="{ paddingLeft: `${10 + level * 14}px` }"
        @click="handleClick"
      >
        <span class="memory-icon">
          {{ isDirectory ? (isExpanded ? '▾' : '▸') : '•' }}
        </span>
        <span class="memory-name">{{ node.name }}</span>
        <span v-if="friendlyLabel" class="memory-tag">{{ friendlyLabel }}</span>
      </button>
      <button
        v-if="showDeleteAction"
        :data-testid="`memory-tree-delete-${node.name}`"
        type="button"
        class="memory-row-delete"
        title="删除此记忆文件"
        @click.stop="emit('request-delete', node.path)"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
          <path d="M10 11v6" />
          <path d="M14 11v6" />
          <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
        </svg>
      </button>
    </div>

    <div v-if="isDirectory && isExpanded && node.children?.length" class="memory-children">
      <MemoryTreeNode
        v-for="child in node.children"
        :key="child.path"
        :node="child"
        :level="level + 1"
        :selected-path="selectedPath"
        :expanded-paths="expandedPaths"
        @select="emit('select', $event)"
        @toggle="emit('toggle', $event)"
        @request-delete="emit('request-delete', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.memory-node {
  display: flex;
  flex-direction: column;
}

.memory-row-shell {
  display: flex;
  align-items: center;
  gap: 6px;
  border-radius: 4px;
  transition: background 0.12s ease, color 0.12s ease;
}

.memory-row-shell:hover {
  background: var(--hover);
}

.memory-row-shell.active {
  background: var(--selection);
  color: var(--accent);
  box-shadow: inset 0 0 0 1px var(--border);
}

.memory-row-shell.active-branch {
  color: var(--text);
}

.memory-row {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  min-height: 30px;
  padding: 6px 10px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-strong);
  text-align: left;
  cursor: pointer;
  transition: color 0.12s ease;
  flex: 1;
}

.memory-row-shell.active .memory-row {
  color: var(--accent);
}

.memory-row-shell.active-branch .memory-row {
  color: var(--text);
}

.memory-row-dir {
  font-size: 12px;
  font-weight: 500;
}

.memory-row-file {
  font-size: 12px;
}

.memory-icon {
  width: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.memory-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.memory-tag {
  color: var(--text-muted);
  font-size: 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 1px 6px;
  flex-shrink: 0;
}

.memory-row-delete {
  margin-right: 6px;
  border: none;
  border-radius: 5px;
  background: transparent;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  cursor: pointer;
  flex-shrink: 0;
  opacity: 0.72;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    opacity 0.15s ease;
}

.memory-row-shell:hover .memory-row-delete,
.memory-row-shell.active .memory-row-delete {
  opacity: 1;
}

.memory-row-delete:hover {
  background: rgba(200, 111, 100, 0.14);
  color: var(--danger) !important;
  opacity: 1 !important;
}

.memory-row:focus-visible,
.memory-row-delete:focus-visible {
  outline: 1px solid var(--accent);
  outline-offset: 1px;
}

.memory-children {
  display: flex;
  flex-direction: column;
}
</style>

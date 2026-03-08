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
}>()

const isDirectory = computed(() => props.node.kind === 'directory')
const isExpanded = computed(() => props.expandedPaths.includes(props.node.path))
const isActiveBranch = computed(() => {
  if (!props.selectedPath) return false
  return props.selectedPath === props.node.path || props.selectedPath.startsWith(props.node.path)
})

const friendlyLabels: Record<string, string> = {
  'instructions.txt': '系统指令',
  'hosts.txt': '主机清单',
  'user_preferences.txt': '用户偏好',
  'ops': '运维记录',
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
    <button
      class="memory-row"
      :class="{
        'memory-row-dir': isDirectory,
        'memory-row-file': !isDirectory,
        'active': selectedPath === node.path,
        'active-branch': isDirectory && isActiveBranch,
      }"
      :style="{ paddingLeft: `${10 + level * 14}px` }"
      @click="handleClick"
    >
      <span class="memory-icon">
        {{ isDirectory ? (isExpanded ? '▾' : '▸') : '•' }}
      </span>
      <span class="memory-name">{{ node.name }}</span>
      <span v-if="friendlyLabel" class="memory-tag">{{ friendlyLabel }}</span>
    </button>

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
      />
    </div>
  </div>
</template>

<style scoped>
.memory-node {
  display: flex;
  flex-direction: column;
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
  color: var(--text-bright);
  text-align: left;
  cursor: pointer;
  transition: background 0.12s ease, color 0.12s ease;
}

.memory-row:hover {
  background: var(--bg-hover);
}

.memory-row.active {
  background: var(--selection);
  color: var(--cyan);
}

.memory-row.active-branch {
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
  color: var(--text-dim);
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
  color: var(--text-dim);
  font-size: 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 1px 6px;
  flex-shrink: 0;
}

.memory-children {
  display: flex;
  flex-direction: column;
}
</style>

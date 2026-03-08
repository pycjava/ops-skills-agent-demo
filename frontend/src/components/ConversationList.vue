<script setup lang="ts">
import { ref, watch } from 'vue'
import type { ConversationItem } from '../stores/chat'

defineProps<{
  conversations: ConversationItem[]
  currentId: string | null
}>()

const emit = defineEmits<{
  (e: 'select', id: string): void
  (e: 'create'): void
  (e: 'delete', id: string): void
  (e: 'search', query: string): void
}>()

const searchQuery = ref('')
let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(searchQuery, (value) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    emit('search', value)
  }, 300)
})

function formatTime(iso: string | null): string {
  if (!iso) return ''

  const date = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  if (diff < 604_800_000) return `${Math.floor(diff / 86_400_000)} 天前`

  return `${date.getMonth() + 1}/${date.getDate()}`
}
</script>

<template>
  <div class="conv-list">
    <button class="new-conv" @click="emit('create')">
      <span class="plus">＋</span>
      <span>新对话</span>
    </button>

    <div class="list-section">
      <div class="section-title">历史对话</div>

      <div class="search-box">
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          placeholder="搜索历史对话"
        />
        <span class="search-icon">⌕</span>
      </div>
    </div>

    <div class="list">
      <div
        v-for="conv in conversations"
        :key="conv.id"
        class="conv-item"
        :class="{ active: conv.id === currentId }"
        @click="emit('select', conv.id)"
      >
        <div class="conv-main">
          <div class="conv-title-row">
            <span v-if="conv.source === 'api'" class="api-badge">API</span>
            <span class="conv-title">{{ conv.title || '新对话' }}</span>
          </div>
          <span class="conv-time">{{ formatTime(conv.updated_at) }}</span>
        </div>

        <button class="del-btn" title="删除会话" @click.stop="emit('delete', conv.id)">
          ✕
        </button>
      </div>

      <div v-if="conversations.length === 0" class="empty">
        <span class="empty-text">
          {{ searchQuery ? '没有找到匹配的会话' : '还没有历史对话' }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.conv-list {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 4px 12px 16px;
}

.new-conv {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  margin: 6px 0 18px;
  padding: 14px 18px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.45);
  color: var(--text-strong);
  cursor: pointer;
  transition:
    transform 0.15s ease,
    border-color 0.15s ease,
    background 0.15s ease;
}

.new-conv:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  background: var(--card-strong);
}

.plus {
  font-size: 15px;
  font-weight: 700;
}

.list-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.section-title {
  padding: 0 6px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.search-box {
  position: relative;
}

.search-input {
  width: 100%;
  height: 42px;
  padding: 0 38px 0 14px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.45);
  color: var(--text-strong);
  outline: none;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.search-input:focus {
  border-color: var(--border-strong);
  background: var(--card-strong);
}

.search-input::placeholder {
  color: var(--text-soft);
}

.search-icon {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-soft);
  pointer-events: none;
}

.list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 2px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.list::-webkit-scrollbar {
  width: 6px;
}

.list::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 999px;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 10px 12px 12px;
  border-radius: 16px;
  cursor: pointer;
  transition:
    background 0.15s ease,
    transform 0.15s ease;
}

.conv-item:hover {
  background: var(--selection);
}

.conv-item.active {
  background: var(--hover);
}

.conv-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.conv-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.conv-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-strong);
  font-size: 14px;
  font-weight: 500;
}

.api-badge {
  padding: 3px 6px;
  border-radius: 999px;
  background: rgba(139, 115, 255, 0.12);
  color: var(--accent);
  font-size: 10px;
  font-weight: 700;
}

.conv-time {
  color: var(--text-muted);
  font-size: 12px;
}

.del-btn {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--text-soft);
  cursor: pointer;
  opacity: 0;
  transition:
    opacity 0.15s ease,
    background 0.15s ease,
    color 0.15s ease;
}

.conv-item:hover .del-btn,
.conv-item.active .del-btn {
  opacity: 1;
}

.del-btn:hover {
  background: rgba(200, 111, 100, 0.12);
  color: var(--danger);
}

.empty {
  padding: 18px 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.22);
}

.empty-text {
  color: var(--text-muted);
  font-size: 13px;
}
</style>

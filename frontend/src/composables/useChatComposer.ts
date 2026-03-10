import { computed, nextTick, ref, watch, type ComputedRef } from 'vue'
import type { Skill } from '../stores/chat'

const HOME_COMPOSER_MIN_HEIGHT = 48
const HOME_COMPOSER_MAX_HEIGHT = 320
const CHAT_COMPOSER_MIN_HEIGHT = 36
const CHAT_COMPOSER_MAX_HEIGHT = 220

interface UseChatComposerOptions {
  hasMessages: ComputedRef<boolean>
  isConnected: ComputedRef<boolean>
  isLoading: ComputedRef<boolean>
  skills: ComputedRef<Skill[]>
  sendMessage: (displayContent: string, sendContent?: string) => void
}

function buildImplicitSkillPrompt(text: string, skills: Skill[]): string {
  const matches = text.match(/@([\w-]+)/g)
  if (!matches) {
    return ''
  }

  const mentionedSkills = matches
    .map((match) => match.slice(1))
    .filter((name) => skills.some((skill) => skill.id === name))

  if (mentionedSkills.length === 0) {
    return ''
  }

  const uniqueSkills = [...new Set(mentionedSkills)]
  return `\n\n<system_hint>\n[系统内部指令：用户已明确指定使用工具 ${uniqueSkills
    .map((skill) => `"${skill}"`)
    .join(', ')}。请优先、立即调用这些工具来处理请求，在工具返回结果之前不要做多余回答。]\n</system_hint>`
}

export function useChatComposer({
  hasMessages,
  isConnected,
  isLoading,
  skills,
  sendMessage,
}: UseChatComposerOptions) {
  const inputText = ref('')
  const composerInput = ref<HTMLTextAreaElement | null>(null)
  const showMentions = ref(false)
  const mentionSearch = ref('')
  const mentionIndex = ref(0)

  const filteredSkills = computed(() => {
    if (!showMentions.value) return []

    const search = mentionSearch.value.toLowerCase()
    return skills.value.filter(
      (skill) =>
        skill.id.toLowerCase().includes(search) || skill.name.toLowerCase().includes(search),
    )
  })

  const inputPlaceholder = computed(() =>
    hasMessages.value ? '发送消息...' : '给我发消息或布置任务',
  )

  const canSend = computed(
    () => Boolean(inputText.value.trim()) && isConnected.value && !isLoading.value,
  )

  function resizeComposerInput() {
    const textarea = composerInput.value
    if (!textarea) return

    const minHeight = hasMessages.value ? CHAT_COMPOSER_MIN_HEIGHT : HOME_COMPOSER_MIN_HEIGHT
    const maxHeight = hasMessages.value ? CHAT_COMPOSER_MAX_HEIGHT : HOME_COMPOSER_MAX_HEIGHT

    textarea.style.height = 'auto'

    const nextHeight = Math.min(Math.max(textarea.scrollHeight, minHeight), maxHeight)
    textarea.style.height = `${nextHeight}px`
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden'
  }

  function scrollActiveIntoView() {
    nextTick(() => {
      const popup = document.querySelector('.mentions-popup')
      const active = popup?.querySelector('.mention-item.active') as HTMLElement | null
      if (active && popup) {
        active.scrollIntoView({ block: 'nearest' })
      }
    })
  }

  function updateMentionState() {
    const match = inputText.value.match(/@([\w-]*)$/)
    if (match) {
      showMentions.value = true
      mentionSearch.value = match[1] || ''
      mentionIndex.value = 0
      return
    }

    showMentions.value = false
    mentionSearch.value = ''
  }

  function handleInput() {
    resizeComposerInput()
    updateMentionState()
  }

  function selectMention(skillName: string) {
    inputText.value = inputText.value.replace(/@([\w-]*)$/, `@${skillName} `)
    showMentions.value = false
    mentionSearch.value = ''
    mentionIndex.value = 0
    nextTick(() => resizeComposerInput())
  }

  function handleSend() {
    const normalizedText = inputText.value.trim()
    if (!normalizedText || isLoading.value || !isConnected.value) return

    const implicitPrompt = buildImplicitSkillPrompt(normalizedText, skills.value)
    sendMessage(normalizedText, normalizedText + implicitPrompt)
    inputText.value = ''
    showMentions.value = false
    mentionSearch.value = ''
    mentionIndex.value = 0
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (showMentions.value && filteredSkills.value.length > 0) {
      if (event.key === 'ArrowUp') {
        event.preventDefault()
        event.stopPropagation()
        mentionIndex.value =
          (mentionIndex.value - 1 + filteredSkills.value.length) % filteredSkills.value.length
        scrollActiveIntoView()
        return
      }

      if (event.key === 'ArrowDown') {
        event.preventDefault()
        event.stopPropagation()
        mentionIndex.value = (mentionIndex.value + 1) % filteredSkills.value.length
        scrollActiveIntoView()
        return
      }

      if (event.key === 'Enter' || event.key === 'Tab') {
        event.preventDefault()
        const selectedSkill = filteredSkills.value[mentionIndex.value]
        if (selectedSkill) {
          selectMention(selectedSkill.id)
        }
        return
      }

      if (event.key === 'Escape') {
        showMentions.value = false
        mentionSearch.value = ''
        return
      }
    }

    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault()
      handleSend()
    }
  }

  function sendQuickPrompt(prompt: string) {
    if (!prompt.trim() || isLoading.value || !isConnected.value) return
    sendMessage(prompt)
  }

  watch(inputText, () => {
    nextTick(() => resizeComposerInput())
  })

  watch(hasMessages, () => {
    nextTick(() => resizeComposerInput())
  })

  return {
    inputText,
    composerInput,
    showMentions,
    mentionSearch,
    mentionIndex,
    filteredSkills,
    inputPlaceholder,
    canSend,
    handleInput,
    handleKeyDown,
    handleSend,
    selectMention,
    sendQuickPrompt,
    resizeComposerInput,
  }
}

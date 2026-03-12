import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type ComputedRef,
} from 'vue'
import type { AgentInfo } from '../stores/chat'
import { getMillisecondsUntilNextShanghaiMidnight, resolveGreeting } from '../utils/greeting'

export type InspectorTab = 'skills' | 'mcp' | 'memory'

interface UseAppChromeOptions {
  agents: ComputedRef<AgentInfo[]>
  setDraftAgent: (agentId: string) => void
  connect: () => void
  fetchAgents: () => Promise<void>
  fetchConversations: () => Promise<void>
  fetchTaskNotifications: () => Promise<void>
  fetchSkills: (agentId?: string) => Promise<void>
  fetchMcpServers: () => Promise<void>
  fetchMemoryTree: (force?: boolean) => Promise<void>
  openMemoryDocument: (path: string) => Promise<void>
  resizeComposerInput: () => void
}

export function useAppChrome({
  agents,
  setDraftAgent,
  connect,
  fetchAgents,
  fetchConversations,
  fetchTaskNotifications,
  fetchSkills,
  fetchMcpServers,
  fetchMemoryTree,
  openMemoryDocument,
  resizeComposerInput,
}: UseAppChromeOptions) {
  const showSidebar = ref(true)
  const isDark = ref(localStorage.getItem('theme') === 'dark')
  const showInspector = ref(false)
  const showAgentOverflowMenu = ref(false)
  const rightPanelTab = ref<InspectorTab>('skills')
  const currentTime = ref(new Date())
  const pendingMemoryOpenPath = ref<string | null>(null)
  const visibleAgentCount = ref(Number.POSITIVE_INFINITY)
  const agentSelector = ref<HTMLElement | null>(null)
  const agentSelectorWrap = ref<HTMLElement | null>(null)
  const moreMeasureRef = ref<HTMLElement | null>(null)
  const agentMeasureRefs = ref<HTMLElement[]>([])

  const heroTitle = computed(() => resolveGreeting(currentTime.value).title)
  const visibleAgents = computed(() => agents.value.slice(0, visibleAgentCount.value))
  const overflowAgents = computed(() => agents.value.slice(visibleAgentCount.value))

  let greetingRefreshTimer: ReturnType<typeof setTimeout> | null = null

  function clearGreetingRefreshTimer() {
    if (!greetingRefreshTimer) return
    clearTimeout(greetingRefreshTimer)
    greetingRefreshTimer = null
  }

  function syncGreetingClock() {
    currentTime.value = new Date()
    clearGreetingRefreshTimer()
    greetingRefreshTimer = setTimeout(
      syncGreetingClock,
      getMillisecondsUntilNextShanghaiMidnight(currentTime.value) + 50,
    )
  }

  function setAgentMeasureRef(element: unknown, index: number) {
    const target =
      element instanceof HTMLElement
        ? element
        : element &&
            typeof element === 'object' &&
            '$el' in element &&
            element.$el instanceof HTMLElement
          ? element.$el
          : null

    if (!target) return
    agentMeasureRefs.value[index] = target
  }

  function closeAgentOverflowMenu() {
    showAgentOverflowMenu.value = false
  }

  function toggleAgentOverflowMenu() {
    showAgentOverflowMenu.value = !showAgentOverflowMenu.value
  }

  function selectAgent(agentId: string) {
    setDraftAgent(agentId)
    closeAgentOverflowMenu()
  }

  function recalculateVisibleAgents() {
    nextTick(() => {
      if (!agentSelector.value) {
        visibleAgentCount.value = agents.value.length
        return
      }

      const containerWidth = agentSelector.value.clientWidth
      const gap = 10
      const itemWidths = agents.value
        .map((_, index) => agentMeasureRefs.value[index]?.offsetWidth ?? 0)
        .filter((width) => width > 0)

      if (itemWidths.length === 0) {
        visibleAgentCount.value = agents.value.length
        return
      }

      const moreWidth = moreMeasureRef.value?.offsetWidth ?? 0
      let usedWidth = 0
      let count = 0

      for (let index = 0; index < itemWidths.length; index += 1) {
        const itemWidth = itemWidths[index] ?? 0
        const nextWidth = usedWidth + (count > 0 ? gap : 0) + itemWidth
        const hasHiddenItems = index < itemWidths.length - 1
        const reservedForMore = hasHiddenItems ? gap + moreWidth : 0

        if (nextWidth + reservedForMore <= containerWidth) {
          usedWidth = nextWidth
          count += 1
          continue
        }

        break
      }

      if (count === 0 && agents.value.length > 0) {
        visibleAgentCount.value = 1
        return
      }

      visibleAgentCount.value = count
    })
  }

  function handleDocumentClick(event: MouseEvent) {
    if (!showAgentOverflowMenu.value) return

    const target = event.target
    if (!(target instanceof Node)) return
    if (agentSelectorWrap.value?.contains(target)) return
    closeAgentOverflowMenu()
  }

  function handleWindowResize() {
    recalculateVisibleAgents()
    resizeComposerInput()
  }

  function openInspector(tab: InspectorTab = 'skills') {
    rightPanelTab.value = tab
    showInspector.value = true
  }

  function closeInspector() {
    showInspector.value = false
  }

  async function handleOpenMemory(path: string) {
    if (!path.startsWith('/memories/')) return

    pendingMemoryOpenPath.value = path
    rightPanelTab.value = 'memory'
    showInspector.value = true

    try {
      await nextTick()
      await openMemoryDocument(path)
    } finally {
      pendingMemoryOpenPath.value = null
    }
  }

  function toggleTheme() {
    isDark.value = !isDark.value
    const theme = isDark.value ? 'dark' : 'light'
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }

  onMounted(async () => {
    document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
    syncGreetingClock()
    document.addEventListener('click', handleDocumentClick)
    window.addEventListener('resize', handleWindowResize)
    connect()
    await fetchAgents()
    await fetchConversations()
    await fetchTaskNotifications()
    await fetchSkills()
    await fetchMcpServers()
    await nextTick()
    resizeComposerInput()
    recalculateVisibleAgents()
  })

  onBeforeUnmount(() => {
    clearGreetingRefreshTimer()
    document.removeEventListener('click', handleDocumentClick)
    window.removeEventListener('resize', handleWindowResize)
  })

  watch([rightPanelTab, showInspector], ([tab, visible]) => {
    if (visible && tab === 'memory' && !pendingMemoryOpenPath.value) {
      void fetchMemoryTree(true)
    }
  })

  watch(
    () => agents.value.map((agent) => `${agent.id}:${agent.label}`).join('|'),
    () => {
      showAgentOverflowMenu.value = false
      agentMeasureRefs.value = []
      recalculateVisibleAgents()
    },
  )

  watch(showSidebar, () => {
    recalculateVisibleAgents()
  })

  return {
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
  }
}

import type { Ref } from 'vue'
import type { ArtifactKind, MemoryDocument, MemoryNode } from './types'

interface MemoryDomainDeps {
  backendUrl: string
  memoryTree: Ref<MemoryNode[]>
  selectedMemoryPath: Ref<string | null>
  memoryContent: Ref<MemoryDocument | null>
  memoryError: Ref<string | null>
  isMemoryTreeLoading: Ref<boolean>
  isMemoryContentLoading: Ref<boolean>
  isMemoryDeleting: Ref<boolean>
  isMemoryTreeLoaded: Ref<boolean>
}

function findFirstMemoryFile(nodes: MemoryNode[]): string | null {
  for (const node of nodes) {
    if (node.kind === 'file') return node.path
    if (node.children?.length) {
      const childPath = findFirstMemoryFile(node.children)
      if (childPath) return childPath
    }
  }

  return null
}

function treeContainsPath(nodes: MemoryNode[], targetPath: string): boolean {
  for (const node of nodes) {
    if (node.path === targetPath) return true
    if (node.children?.length && treeContainsPath(node.children, targetPath)) {
      return true
    }
  }

  return false
}

function getToolPath(toolInput?: Record<string, unknown>): string | null {
  const value = toolInput?.file_path ?? toolInput?.path
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

export function normalizeArtifactKind(value: unknown): ArtifactKind | undefined {
  return value === 'memory' || value === 'report' || value === 'file' ? value : undefined
}

export function createMemoryDomain({
  backendUrl,
  memoryTree,
  selectedMemoryPath,
  memoryContent,
  memoryError,
  isMemoryTreeLoading,
  isMemoryContentLoading,
  isMemoryDeleting,
  isMemoryTreeLoaded,
}: MemoryDomainDeps) {
  async function fetchMemoryTree(force = false) {
    if (isMemoryTreeLoading.value) return
    if (isMemoryTreeLoaded.value && !force) return

    isMemoryTreeLoading.value = true
    memoryError.value = null

    try {
      const res = await fetch(`${backendUrl}/api/memories/tree`)
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      const tree: MemoryNode[] = await res.json()
      memoryTree.value = tree
      isMemoryTreeLoaded.value = true

      const nextPath =
        selectedMemoryPath.value && treeContainsPath(tree, selectedMemoryPath.value)
          ? selectedMemoryPath.value
          : findFirstMemoryFile(tree)

      if (!nextPath) {
        selectedMemoryPath.value = null
        memoryContent.value = null
        return
      }

      if (force || memoryContent.value?.path !== nextPath) {
        await fetchMemoryContent(nextPath)
      }
    } catch (error) {
      memoryError.value = '加载记忆失败'
      console.warn('加载记忆树失败:', error)
      if (!memoryTree.value.length) {
        selectedMemoryPath.value = null
        memoryContent.value = null
      }
    } finally {
      isMemoryTreeLoading.value = false
    }
  }

  async function fetchMemoryContent(path: string) {
    if (!path) return

    selectedMemoryPath.value = path
    isMemoryContentLoading.value = true
    memoryError.value = null

    try {
      const res = await fetch(
        `${backendUrl}/api/memories/content?path=${encodeURIComponent(path)}`,
      )
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      memoryContent.value = await res.json()
    } catch (error) {
      memoryContent.value = null
      memoryError.value = '读取记忆失败'
      console.warn('读取记忆文档失败:', error)
    } finally {
      isMemoryContentLoading.value = false
    }
  }

  async function deleteMemoryFile(path: string) {
    if (!path || isMemoryDeleting.value) return

    isMemoryDeleting.value = true
    memoryError.value = null

    try {
      const res = await fetch(
        `${backendUrl}/api/memories/content?path=${encodeURIComponent(path)}`,
        { method: 'DELETE' },
      )
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      if (selectedMemoryPath.value === path) {
        memoryContent.value = null
      }

      await fetchMemoryTree(true)
    } catch (error) {
      memoryError.value = '删除记忆失败'
      console.warn('删除记忆文件失败:', error)
    } finally {
      isMemoryDeleting.value = false
    }
  }

  async function openMemoryDocument(path: string) {
    if (!path || !path.startsWith('/memories/')) return

    selectedMemoryPath.value = path
    await fetchMemoryTree(true)

    if (memoryContent.value?.path !== path) {
      await fetchMemoryContent(path)
    }
  }

  function handleMemoryArtifact(toolInput?: Record<string, unknown>) {
    const path = getToolPath(toolInput)
    if (!path || !path.startsWith('/memories/')) return

    if (isMemoryTreeLoaded.value) {
      void fetchMemoryTree(true)
      return
    }

    isMemoryTreeLoaded.value = false
  }

  return {
    fetchMemoryTree,
    fetchMemoryContent,
    deleteMemoryFile,
    openMemoryDocument,
    handleMemoryArtifact,
  }
}

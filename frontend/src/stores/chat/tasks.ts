import type { Ref } from 'vue'

import { readErrorMessage } from './helpers'
import type { InspectionTask, InspectionTaskDraft, InspectionTaskRun } from './types'

interface TaskDomainDeps {
  backendUrl: string
  inspectionTasks: Ref<InspectionTask[]>
  inspectionTaskRuns: Ref<InspectionTaskRun[]>
  inspectionTaskError: Ref<string | null>
  isInspectionTaskLoading: Ref<boolean>
}

function replaceTask(tasks: Ref<InspectionTask[]>, task: InspectionTask) {
  const index = tasks.value.findIndex((item) => item.id === task.id)
  if (index === -1) {
    tasks.value = [task, ...tasks.value]
    return
  }

  tasks.value = tasks.value.map((item, itemIndex) => (itemIndex === index ? task : item))
}

export function createTaskDomain({
  backendUrl,
  inspectionTasks,
  inspectionTaskRuns,
  inspectionTaskError,
  isInspectionTaskLoading,
}: TaskDomainDeps) {
  async function fetchInspectionTasks() {
    isInspectionTaskLoading.value = true
    inspectionTaskError.value = null

    try {
      const res = await fetch(`${backendUrl}/api/inspection-tasks`)
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
      }
      inspectionTasks.value = await res.json()
    } catch (error) {
      inspectionTaskError.value =
        error instanceof Error ? error.message : '加载定时任务失败'
      console.warn('加载定时任务失败:', error)
    } finally {
      isInspectionTaskLoading.value = false
    }
  }

  async function fetchInspectionTaskRuns(taskId?: string) {
    isInspectionTaskLoading.value = true
    inspectionTaskError.value = null

    try {
      const url = taskId
        ? `${backendUrl}/api/inspection-tasks/${encodeURIComponent(taskId)}/runs`
        : `${backendUrl}/api/inspection-tasks/runs/all`
      const res = await fetch(url)
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
      }
      inspectionTaskRuns.value = await res.json()
    } catch (error) {
      inspectionTaskError.value =
        error instanceof Error ? error.message : '加载执行记录失败'
      console.warn('加载执行记录失败:', error)
    } finally {
      isInspectionTaskLoading.value = false
    }
  }

  async function buildInspectionTaskDraft(
    conversationId: string,
  ): Promise<InspectionTaskDraft | null> {
    inspectionTaskError.value = null
    const res = await fetch(`${backendUrl}/api/inspection-tasks/draft`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        conversation_id: conversationId,
      }),
    })

    if (!res.ok) {
      const message = await readErrorMessage(res, `HTTP ${res.status}`)
      inspectionTaskError.value = message
      return null
    }

    return (await res.json()) as InspectionTaskDraft
  }

  async function createInspectionTask(payload: InspectionTaskDraft): Promise<InspectionTask | null> {
    inspectionTaskError.value = null
    const res = await fetch(`${backendUrl}/api/inspection-tasks`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })

    if (!res.ok) {
      const message = await readErrorMessage(res, `HTTP ${res.status}`)
      inspectionTaskError.value = message
      return null
    }

    const task = (await res.json()) as InspectionTask
    replaceTask(inspectionTasks, task)
    return task
  }

  async function updateInspectionTask(
    taskId: string,
    payload: Partial<InspectionTaskDraft>,
  ): Promise<InspectionTask | null> {
    inspectionTaskError.value = null
    const res = await fetch(`${backendUrl}/api/inspection-tasks/${encodeURIComponent(taskId)}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })

    if (!res.ok) {
      const message = await readErrorMessage(res, `HTTP ${res.status}`)
      inspectionTaskError.value = message
      return null
    }

    const task = (await res.json()) as InspectionTask
    replaceTask(inspectionTasks, task)
    return task
  }

  async function triggerInspectionTask(taskId: string): Promise<InspectionTaskRun | null> {
    inspectionTaskError.value = null
    const res = await fetch(
      `${backendUrl}/api/inspection-tasks/${encodeURIComponent(taskId)}/trigger`,
      {
        method: 'POST',
      },
    )

    if (!res.ok) {
      const message = await readErrorMessage(res, `HTTP ${res.status}`)
      inspectionTaskError.value = message
      return null
    }

    const run = (await res.json()) as InspectionTaskRun
    inspectionTaskRuns.value = [run, ...inspectionTaskRuns.value]
    void fetchInspectionTasks()
    return run
  }

  return {
    fetchInspectionTasks,
    fetchInspectionTaskRuns,
    buildInspectionTaskDraft,
    createInspectionTask,
    updateInspectionTask,
    triggerInspectionTask,
  }
}

import type { Ref } from 'vue'

import { apiFetch, readErrorMessage } from './helpers'
import type {
  InspectionTask,
  InspectionTaskDraft,
  InspectionTaskFromConversationMessageResult,
  InspectionTaskRun,
} from './types'

// SSE 事件类型
export type TaskStreamEvent =
  | { type: 'tool_call'; tool_name: string; tool_desc: string; tool_input?: Record<string, unknown> }
  | { type: 'tool_result'; tool_name: string; result: string; tool_input?: Record<string, unknown> }
  | { type: 'clarification_needed'; content: string; original_message?: string }
  | { type: 'done'; status: 'created'; task: InspectionTask; intent_analysis?: unknown }
  | { type: 'done'; status: 'error'; message: string; intent_analysis?: unknown }
  | { type: 'done'; status: 'clarification_needed'; message: string; clarification_prompt: string; intent_analysis?: unknown }
  | { type: 'done'; status: 'not_task_creation' }
  | { type: 'error'; content: string }

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

function removeTask(tasks: Ref<InspectionTask[]>, taskId: string) {
  tasks.value = tasks.value.filter((item) => item.id !== taskId)
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
      const res = await apiFetch(`${backendUrl}/api/inspection-tasks`)
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
      const res = await apiFetch(url)
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
    const res = await apiFetch(`${backendUrl}/api/inspection-tasks/draft`, {
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
    const res = await apiFetch(`${backendUrl}/api/inspection-tasks`, {
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

  async function createInspectionTaskFromConversationMessage(
    conversationId: string,
    message: string,
  ): Promise<InspectionTaskFromConversationMessageResult | null> {
    inspectionTaskError.value = null
    const res = await apiFetch(`${backendUrl}/api/inspection-tasks/from-conversation-message`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        conversation_id: conversationId,
        message,
      }),
    })

    if (!res.ok) {
      const message = await readErrorMessage(res, `HTTP ${res.status}`)
      inspectionTaskError.value = message
      return null
    }

    const result = (await res.json()) as InspectionTaskFromConversationMessageResult
    if (result.status === 'created') {
      replaceTask(inspectionTasks, result.task)
      return result
    }

    if (result.status === 'error') {
      inspectionTaskError.value = result.message
    }

    return result
  }

  /**
   * 以 SSE 流式方式生成定时任务。
   * 每收到一个 SSE 事件就调用 onEvent 回调，调用方可实时将事件注入消息列表。
   * 最终返回 done 事件中的结果（status/task/intent_analysis）。
   */
  async function createInspectionTaskFromConversationMessageStream(
    conversationId: string,
    message: string,
    onEvent: (event: TaskStreamEvent) => void,
    previousContext?: { original_message: string },
  ): Promise<InspectionTaskFromConversationMessageResult | null> {
    inspectionTaskError.value = null

    let res: Response
    try {
      res = await apiFetch(`${backendUrl}/api/inspection-tasks/from-conversation-message/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: conversationId,
          message,
          previous_context: previousContext,
        }),
      })
    } catch (err) {
      inspectionTaskError.value = err instanceof Error ? err.message : '网络错误'
      return null
    }

    if (!res.ok || !res.body) {
      const errMsg = await readErrorMessage(res, `HTTP ${res.status}`)
      inspectionTaskError.value = errMsg
      return null
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalResult: InspectionTaskFromConversationMessageResult | null = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const jsonStr = line.slice(6).trim()
        if (!jsonStr) continue

        let event: TaskStreamEvent
        try {
          event = JSON.parse(jsonStr) as TaskStreamEvent
        } catch {
          continue
        }

        onEvent(event)

        if (event.type === 'done') {
          if (event.status === 'created') {
            replaceTask(inspectionTasks, event.task)
            finalResult = {
              status: 'created',
              task: event.task,
              intent_analysis: event.intent_analysis as never,
            }
          } else if (event.status === 'error') {
            inspectionTaskError.value = event.message
            finalResult = {
              status: 'error',
              message: event.message,
              intent_analysis: event.intent_analysis as never,
            }
          } else if (event.status === 'clarification_needed') {
            finalResult = {
              status: 'clarification_needed',
              message: event.message,
              clarification_prompt: event.clarification_prompt,
              intent_analysis: event.intent_analysis as never,
            }
          } else {
            finalResult = { status: 'not_task_creation' }
          }
        }

        if (event.type === 'error') {
          inspectionTaskError.value = event.content
          finalResult = { status: 'error', message: event.content }
        }
      }
    }

    return finalResult
  }

  async function updateInspectionTask(
    taskId: string,
    payload: Partial<InspectionTaskDraft>,
  ): Promise<InspectionTask | null> {
    inspectionTaskError.value = null
    const res = await apiFetch(`${backendUrl}/api/inspection-tasks/${encodeURIComponent(taskId)}`, {
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

  async function deleteInspectionTask(taskId: string): Promise<boolean> {
    inspectionTaskError.value = null
    const res = await apiFetch(`${backendUrl}/api/inspection-tasks/${encodeURIComponent(taskId)}`, {
      method: 'DELETE',
    })

    if (!res.ok) {
      const message = await readErrorMessage(res, `HTTP ${res.status}`)
      inspectionTaskError.value = message
      return false
    }

    removeTask(inspectionTasks, taskId)
    inspectionTaskRuns.value = inspectionTaskRuns.value.filter((run) => run.task_id !== taskId)
    return true
  }

  async function triggerInspectionTask(taskId: string): Promise<InspectionTaskRun | null> {
    inspectionTaskError.value = null
    const res = await apiFetch(
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
    createInspectionTaskFromConversationMessage,
    createInspectionTaskFromConversationMessageStream,
    createInspectionTask,
    updateInspectionTask,
    deleteInspectionTask,
    triggerInspectionTask,
  }
}

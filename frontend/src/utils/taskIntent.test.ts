import { describe, expect, test } from 'vitest'

import { isInspectionTaskIntent, suggestCronFromTaskIntent } from './taskIntent'

describe('taskIntent', () => {
  test('detects creating a scheduled task from the current conversation', () => {
    expect(isInspectionTaskIntent('把上述会话做成定时任务，每天 9 点执行')).toBe(true)
    expect(isInspectionTaskIntent('将当前巡检会话设成定时巡检')).toBe(true)
    expect(isInspectionTaskIntent('继续分析这个实例')).toBe(false)
  })

  test('extracts a simple daily cron expression from natural language', () => {
    expect(suggestCronFromTaskIntent('把上述会话做成定时任务，每天 9 点执行')).toBe(
      '0 9 * * *',
    )
    expect(suggestCronFromTaskIntent('把这个会话设成定时任务，每天18:30执行')).toBe(
      '30 18 * * *',
    )
    expect(suggestCronFromTaskIntent('把这个会话做成定时任务')).toBeNull()
  })
})

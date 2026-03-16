const TASK_KEYWORDS = ['定时任务', '定时巡检', '定时执行']
const TASK_ACTION_KEYWORDS = ['创建', '新建', '生成', '做成', '设成', '设置成', '配置', '添加', '安排']
const CONVERSATION_REFERENCE_KEYWORDS = [
  '上述会话',
  '当前会话',
  '这个会话',
  '这段会话',
  '历史会话',
  '该会话',
  '本会话',
  '巡检会话',
  '当前巡检',
]
const QUESTION_HINT_KEYWORDS = ['怎么', '如何', '为何', '为什么', '是什么', '介绍', '解释']
const WEEKDAY_TO_CRON: Record<string, string> = {
  '0': '0',
  '7': '0',
  日: '0',
  天: '0',
  一: '1',
  二: '2',
  三: '3',
  四: '4',
  五: '5',
  六: '6',
}

function normalizeTaskIntentText(value: string): string {
  return value.toLowerCase().replace(/\s+/g, '').trim()
}

function includesAny(value: string, keywords: string[]): boolean {
  return keywords.some((keyword) => value.includes(keyword))
}

function resolveHourAndMinute(hourText: string, minuteText?: string): [number, number] | null {
  const hour = Number(hourText)
  const minute = Number(minuteText || '0')
  if (Number.isNaN(hour) || Number.isNaN(minute)) {
    return null
  }
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    return null
  }
  return [hour, minute]
}

function buildCron(hourText: string, minuteText: string | undefined, dom = '*', month = '*', dow = '*') {
  const resolved = resolveHourAndMinute(hourText, minuteText)
  if (!resolved) return null
  const [hour, minute] = resolved
  return `${minute} ${hour} ${dom} ${month} ${dow}`
}

function hasScheduleHint(value: string): boolean {
  return (
    value.includes('每天') ||
    value.includes('每周') ||
    value.includes('每月') ||
    value.includes('工作日') ||
    value.includes('cron') ||
    /\d{1,2}(?:[:：]\d{1,2}|[点时])/.test(value)
  )
}

export function isInspectionTaskIntent(value: string): boolean {
  const normalized = normalizeTaskIntentText(value)
  if (!normalized) return false

  const hasTaskKeyword = includesAny(normalized, TASK_KEYWORDS)
  if (!hasTaskKeyword) return false

  const hasActionKeyword = includesAny(normalized, TASK_ACTION_KEYWORDS)
  const hasConversationReference = includesAny(normalized, CONVERSATION_REFERENCE_KEYWORDS)
  const scheduleHintPresent = hasScheduleHint(normalized)

  if (!hasActionKeyword && !hasConversationReference && !scheduleHintPresent) {
    return false
  }

  if (
    !hasConversationReference &&
    !scheduleHintPresent &&
    includesAny(normalized, QUESTION_HINT_KEYWORDS)
  ) {
    return false
  }

  return true
}

export function suggestCronFromTaskIntent(value: string): string | null {
  if (!isInspectionTaskIntent(value)) {
    return null
  }

  const normalized = normalizeTaskIntentText(value)

  const workdayMatch = normalized.match(/工作日(\d{1,2})(?:[:：](\d{1,2})|(?:点|时)(\d{1,2})?分?)?/)
  if (workdayMatch) {
    const hourText = workdayMatch[1]
    if (!hourText) return null
    return buildCron(hourText, workdayMatch[2] || workdayMatch[3], '*', '*', '1,2,3,4,5')
  }

  const weeklyMatch = normalized.match(
    /每周([一二三四五六日天07])(\d{1,2})(?:[:：](\d{1,2})|(?:点|时)(\d{1,2})?分?)?/,
  )
  if (weeklyMatch) {
    const weekdayKey = weeklyMatch[1]
    const hourText = weeklyMatch[2]
    if (!weekdayKey || !hourText) return null
    const weekday = WEEKDAY_TO_CRON[weekdayKey]
    if (!weekday) return null
    return buildCron(hourText, weeklyMatch[3] || weeklyMatch[4], '*', '*', weekday)
  }

  const monthlyMatch = normalized.match(
    /每月(\d{1,2})(?:号|日)(\d{1,2})(?:[:：](\d{1,2})|(?:点|时)(\d{1,2})?分?)?/,
  )
  if (monthlyMatch) {
    const dayText = monthlyMatch[1]
    const hourText = monthlyMatch[2]
    if (!dayText || !hourText) return null
    const day = Number(dayText)
    if (Number.isNaN(day) || day < 1 || day > 31) {
      return null
    }
    return buildCron(hourText, monthlyMatch[3] || monthlyMatch[4], String(day))
  }

  const dailyMatch = normalized.match(/每天(\d{1,2})(?:[:：](\d{1,2})|(?:点|时)(\d{1,2})?分?)?/)
  if (dailyMatch) {
    const hourText = dailyMatch[1]
    if (!hourText) return null
    return buildCron(hourText, dailyMatch[2] || dailyMatch[3])
  }

  return null
}

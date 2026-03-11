function normalizeTaskIntentText(value: string): string {
  return value.replace(/\s+/g, '').trim()
}

export function isInspectionTaskIntent(value: string): boolean {
  const normalized = normalizeTaskIntentText(value)
  if (!normalized) return false

  return (
    (normalized.includes('定时任务') || normalized.includes('定时巡检')) &&
    (normalized.includes('上述会话') ||
      normalized.includes('当前会话') ||
      normalized.includes('这个会话') ||
      normalized.includes('巡检会话') ||
      normalized.includes('做成') ||
      normalized.includes('设成'))
  )
}

export function suggestCronFromTaskIntent(value: string): string | null {
  if (!isInspectionTaskIntent(value)) {
    return null
  }

  const normalized = normalizeTaskIntentText(value)
  const hhmmMatch = normalized.match(/每天(\d{1,2})[:：点时](\d{1,2})?/)
  if (hhmmMatch) {
    const hour = Number(hhmmMatch[1])
    const minute = Number(hhmmMatch[2] || '0')
    if (hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59) {
      return `${minute} ${hour} * * *`
    }
  }

  return null
}

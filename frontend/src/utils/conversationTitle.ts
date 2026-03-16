export const CONVERSATION_TITLE_MAX_LENGTH = 200

export function normalizeConversationTitle(title: string): string {
  return title.trim()
}

export function getConversationTitleError(title: string): string | null {
  const normalizedTitle = normalizeConversationTitle(title)

  if (!normalizedTitle) {
    return '标题不能为空'
  }

  if (normalizedTitle.length > CONVERSATION_TITLE_MAX_LENGTH) {
    return `标题不能超过 ${CONVERSATION_TITLE_MAX_LENGTH} 个字符`
  }

  return null
}

import type { CloudContextCandidate } from '../stores/chat'

const MYSQL_KEYWORD_RE = /\b(mysql|rds)\b/i
const INSPECTION_KEYWORD_RE =
  /(巡检|健康巡检|健康检查|体检|巡查|inspection|health\s*check)/i
const EXPLICIT_SKILL_RE = /@volcengine-rds-health-analyzer\b/i
const SQL_ANALYSIS_RE = /(执行计划|explain|索引|慢sql|sql\s*(分析|优化|执行)|analyze\s+sql)/i

export function isMysqlInspectionIntent(message: string): boolean {
  const normalizedMessage = message.trim()
  if (!normalizedMessage) return false
  if (SQL_ANALYSIS_RE.test(normalizedMessage)) return false
  if (EXPLICIT_SKILL_RE.test(normalizedMessage)) return true
  return MYSQL_KEYWORD_RE.test(normalizedMessage) && INSPECTION_KEYWORD_RE.test(normalizedMessage)
}

export function getMysqlCandidateLabel(candidate: CloudContextCandidate): string {
  return candidate.instance_name?.trim() || candidate.instance_id?.trim() || '未命名 MySQL 实例'
}

export function getMysqlCandidateMeta(candidate: CloudContextCandidate): string[] {
  return [
    candidate.instance_id?.trim(),
    candidate.project_key?.trim(),
    candidate.region?.trim(),
    candidate.environment?.trim(),
  ].filter((value): value is string => Boolean(value))
}

export function buildMysqlSelectionSystemHint(candidate: CloudContextCandidate): string {
  const details = [
    candidate.instance_id ? `instance_id=${candidate.instance_id}` : null,
    candidate.instance_name ? `instance_name=${candidate.instance_name}` : null,
    candidate.project_key ? `project_key=${candidate.project_key}` : null,
    candidate.region ? `region=${candidate.region}` : null,
    candidate.environment ? `environment=${candidate.environment}` : null,
    candidate.credential_ref ? `credential_ref=${candidate.credential_ref}` : null,
  ]
    .filter((value): value is string => Boolean(value))
    .join('; ')

  if (!details) return ''

  return (
    '\n\n<system_hint>\n' +
    `用户已在界面中明确选择本次巡检目标 MySQL：${details}。` +
    '请优先使用这些已确认信息继续巡检，不要再次要求用户在多个实例之间做选择。\n' +
    '</system_hint>'
  )
}

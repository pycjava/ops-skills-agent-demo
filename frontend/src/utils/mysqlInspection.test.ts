import { describe, expect, test } from 'vitest'
import {
  buildMysqlSelectionSystemHint,
  isMysqlInspectionIntent,
} from './mysqlInspection'

describe('mysqlInspection utils', () => {
  test('recognizes mysql inspection intent without matching sql analysis prompts', () => {
    expect(isMysqlInspectionIntent('帮我巡检 pos 这套 mysql')).toBe(true)
    expect(isMysqlInspectionIntent('请做一个 RDS health check')).toBe(true)
    expect(isMysqlInspectionIntent('帮我分析这条 mysql SQL 为什么慢')).toBe(false)
  })

  test('builds a system hint from the selected mysql candidate', () => {
    const hint = buildMysqlSelectionSystemHint({
      instance_id: 'mysql-123',
      instance_name: 'peets-prod-pos-mysql',
      project_key: 'peets-pos',
      region: 'cn-shanghai',
      environment: 'prod',
      credential_ref: 'volc-peets',
      credential_status: 'configured',
      source: 'instance_override',
    })

    expect(hint).toContain('<system_hint>')
    expect(hint).toContain('mysql-123')
    expect(hint).toContain('peets-prod-pos-mysql')
    expect(hint).toContain('volc-peets')
  })
})

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = readFileSync(resolve(process.cwd(), 'src/components/MemoryTreeNode.vue'), 'utf8')

describe('MemoryTreeNode', () => {
  test('uses the active app theme tokens for hover and selection styles', () => {
    expect(source).not.toContain('var(--bg-hover)')
    expect(source).not.toContain('var(--text-bright)')
    expect(source).not.toContain('var(--text-dim)')
    expect(source).not.toContain('var(--cyan)')
  })

  test('does not fully hide the delete action before hover', () => {
    expect(source).not.toMatch(/\.memory-row-delete\s*\{[\s\S]*?opacity:\s*0;/)
  })
})

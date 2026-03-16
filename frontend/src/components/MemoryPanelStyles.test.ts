import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = readFileSync(resolve(process.cwd(), 'src/components/MemoryPanel.vue'), 'utf8')

describe('MemoryPanel styles', () => {
  test('uses the active app theme tokens instead of legacy memory tokens', () => {
    expect(source).not.toContain('var(--bg-input)')
    expect(source).not.toContain('var(--bg-panel)')
    expect(source).not.toContain('var(--text-bright)')
    expect(source).not.toContain('var(--text-dim)')
    expect(source).not.toContain('var(--cyan)')
  })

  test('keeps the preview header inside narrow panels by allowing shrink and truncation', () => {
    expect(source).toMatch(/\.memory-split\s*\{[\s\S]*?min-width:\s*0;/)
    expect(source).toMatch(/\.memory-section\s*\{[\s\S]*?min-width:\s*0;/)
    expect(source).toMatch(/\.memory-section-head\s*\{[\s\S]*?min-width:\s*0;/)
    expect(source).toMatch(/\.memory-preview-meta\s*\{[\s\S]*?flex:\s*1;[\s\S]*?min-width:\s*0;/)
    expect(source).toMatch(
      /\.memory-document-name\s*\{[\s\S]*?overflow:\s*hidden;[\s\S]*?text-overflow:\s*ellipsis;[\s\S]*?white-space:\s*nowrap;/,
    )
  })
})

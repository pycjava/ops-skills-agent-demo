import { mount } from '@vue/test-utils'
import type { MemoryDocument, MemoryNode } from '../stores/chat'
import MemoryPanel from './MemoryPanel.vue'

const reportPath = '/memories/reports/report-a.md'

const nodes: MemoryNode[] = [
  {
    path: '/memories/reports/',
    name: 'reports',
    kind: 'directory',
    children: [
      {
        path: reportPath,
        name: 'report-a.md',
        kind: 'file',
      },
    ],
  },
]

const reportDocument: MemoryDocument = {
  path: reportPath,
  name: 'report-a.md',
  content: '# report-a',
  updated_at: '2026-03-10T00:00:00Z',
}

function mountMemoryPanel(overrides: Partial<InstanceType<typeof MemoryPanel>['$props']> = {}) {
  return mount(MemoryPanel, {
    props: {
      nodes,
      selectedPath: reportPath,
      document: reportDocument,
      isLoading: false,
      error: null,
      ...overrides,
    },
    global: {
      stubs: { MemoryTreeNode: true },
    },
  })
}

describe('MemoryPanel', () => {
  test('keeps the delete action available for a selected report before preview content loads', async () => {
    const wrapper = mountMemoryPanel()

    const deleteButton = wrapper.get('button.memory-delete')
    expect(deleteButton.attributes('disabled')).toBeUndefined()

    await deleteButton.trigger('click')

    expect(wrapper.find('.memory-confirm').exists()).toBe(true)
    expect(wrapper.text()).toContain('report-a.md')

    await wrapper.get('button.memory-confirm-submit').trigger('click')

    expect(wrapper.emitted('delete')).toEqual([[reportPath]])
  })

  test('shows the delete action in a disabled state while the selected report is loading', () => {
    const wrapper = mountMemoryPanel({
      isLoading: true,
    })

    const deleteButton = wrapper.get('button.memory-delete')
    expect(deleteButton.attributes('disabled')).toBeDefined()
  })

  test('renders a clearly labeled delete action in the preview header', () => {
    const wrapper = mountMemoryPanel()

    expect(wrapper.get('button.memory-delete').text()).toContain('删除')
  })

  test('keeps the preview-header delete action visible after selecting the shown file', async () => {
    const wrapper = mountMemoryPanel({
      selectedPath: null,
    })

    expect(wrapper.find('button.memory-delete').exists()).toBe(true)

    await wrapper.setProps({
      selectedPath: reportPath,
    })

    expect(wrapper.find('button.memory-delete').exists()).toBe(true)
    expect(wrapper.get('button.memory-delete').text()).toContain('删除')
  })

  test('keeps the preview-header delete action visible while selection is loading', async () => {
    const wrapper = mountMemoryPanel({
      selectedPath: null,
    })

    expect(wrapper.find('button.memory-delete').exists()).toBe(true)

    await wrapper.setProps({
      document: null,
      isLoading: true,
      selectedPath: null,
    })

    expect(wrapper.find('button.memory-delete').exists()).toBe(true)
    expect(wrapper.get('button.memory-delete').attributes('disabled')).toBeDefined()
  })
})

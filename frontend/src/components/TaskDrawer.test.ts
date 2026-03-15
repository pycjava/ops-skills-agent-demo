import { mount } from '@vue/test-utils'
import { describe, expect, test } from 'vitest'

import TaskDrawer from './TaskDrawer.vue'

const draft = {
  source_conversation_id: 'conv-1',
  name: 'Peets Daily Inspection',
  agent_id: 'dba',
  skill_id: 'volcengine-rds-health-analyzer',
  prompt_template: 'Inspect peets-prod-pos-mysql for the last 7 days',
  target_payload: { instance_name: 'peets-prod-pos-mysql' },
  schedule_type: 'cron' as const,
  cron_expr: '0 9 * * *',
  enabled: true,
}

describe('TaskDrawer', () => {
  test('renders task cards and emits task actions', async () => {
    const wrapper = mount(TaskDrawer, {
      props: {
        visible: true,
        tasks: [
          {
            id: 'task-1',
            name: 'Peets Daily Inspection',
            source_conversation_id: 'conv-1',
            agent_id: 'dba',
            skill_id: 'volcengine-rds-health-analyzer',
            prompt_template: 'Inspect peets-prod-pos-mysql for the last 7 days',
            target_payload: { instance_name: 'peets-prod-pos-mysql' },
            schedule_type: 'cron',
            cron_expr: '0 9 * * *',
            enabled: true,
            last_run_at: '2026-03-11T08:30:00.000',
            next_run_at: '2026-03-11T09:00:00.000',
            last_status: 'succeeded',
            created_at: '2026-03-11T08:00:00.000',
            updated_at: '2026-03-11T08:30:00.000',
          },
        ],
        runs: [],
        draft: null,
        activeTab: 'tasks',
        isLoading: false,
        isSaving: false,
        error: null,
        canCreateDraft: true,
      },
    })

    expect(wrapper.text()).toContain('Peets Daily Inspection')
    expect(wrapper.text()).toContain('下次执行')

    await wrapper.get('[data-testid="task-trigger-task-1"]').trigger('click')
    await wrapper.get('[data-testid="task-toggle-task-1"]').trigger('click')
    await wrapper.get('[data-testid="task-delete-task-1"]').trigger('click')

    expect(wrapper.emitted('trigger')).toEqual([['task-1']])
    expect(wrapper.emitted('toggle')).toEqual([['task-1', false]])
    expect(wrapper.emitted('delete-task')).toEqual([['task-1']])
  })

  test('renders draft form and emits the confirmed payload', async () => {
    const wrapper = mount(TaskDrawer, {
      props: {
        visible: true,
        tasks: [],
        runs: [],
        draft,
        activeTab: 'draft',
        isLoading: false,
        isSaving: false,
        error: null,
        canCreateDraft: true,
      },
    })

    const cronInput = wrapper.get('[data-testid="task-draft-cron"]')
    await cronInput.setValue('30 8 * * *')
    await wrapper.get('[data-testid="task-draft-save"]').trigger('click')

    expect(wrapper.emitted('save-draft')).toEqual([
      [
        {
          ...draft,
          cron_expr: '30 8 * * *',
        },
      ],
    ])
  })

  test('emits open-draft from the header create button', async () => {
    const wrapper = mount(TaskDrawer, {
      props: {
        visible: true,
        tasks: [],
        runs: [],
        draft: null,
        activeTab: 'tasks',
        isLoading: false,
        isSaving: false,
        error: null,
        canCreateDraft: true,
      },
    })

    await wrapper.get('[data-testid="task-open-draft"]').trigger('click')

    expect(wrapper.emitted('open-draft')).toEqual([[]])
  })

  test('emits the selected run when opening a run conversation', async () => {
    const run = {
      id: 'run-1',
      task_id: 'task-1',
      trigger_type: 'manual' as const,
      status: 'succeeded' as const,
      conversation_id: 'conv-run-1',
      started_at: '2026-03-11T08:30:00.000',
      finished_at: '2026-03-11T08:31:00.000',
      error_message: null,
    }

    const wrapper = mount(TaskDrawer, {
      props: {
        visible: true,
        tasks: [],
        runs: [run],
        draft: null,
        activeTab: 'runs',
        isLoading: false,
        isSaving: false,
        error: null,
        canCreateDraft: true,
      },
    })

    await wrapper.get('[data-testid="task-run-open-run-1"]').trigger('click')

    expect(wrapper.emitted('open-conversation')).toEqual([[run]])
  })

  test('shows report download for runs with report_path and emits the selected run', async () => {
    const run = {
      id: 'run-1',
      task_id: 'task-1',
      trigger_type: 'manual' as const,
      status: 'succeeded' as const,
      conversation_id: 'conv-run-1',
      started_at: '2026-03-11T08:30:00.000',
      finished_at: '2026-03-11T08:31:00.000',
      error_message: null,
      report_name: 'report-a.md',
      report_path: '/memories/reports/report-a.md',
    }

    const wrapper = mount(TaskDrawer, {
      props: {
        visible: true,
        tasks: [],
        runs: [run],
        draft: null,
        activeTab: 'runs',
        isLoading: false,
        isSaving: false,
        error: null,
        canCreateDraft: true,
      },
    })

    await wrapper.get('[data-testid="task-run-download-run-1"]').trigger('click')

    expect(wrapper.emitted('download-report')).toEqual([[run]])
  })

  test('shows the task name for each run by matching task_id', () => {
    const wrapper = mount(TaskDrawer, {
      props: {
        visible: true,
        tasks: [
          {
            id: 'task-1',
            name: 'Peets Daily Inspection',
            source_conversation_id: 'conv-1',
            agent_id: 'dba',
            skill_id: 'volcengine-rds-health-analyzer',
            prompt_template: 'Inspect peets-prod-pos-mysql for the last 7 days',
            target_payload: { instance_name: 'peets-prod-pos-mysql' },
            schedule_type: 'cron',
            cron_expr: '0 9 * * *',
            enabled: true,
            last_run_at: '2026-03-11T08:30:00.000',
            next_run_at: '2026-03-11T09:00:00.000',
            last_status: 'succeeded',
            created_at: '2026-03-11T08:00:00.000',
            updated_at: '2026-03-11T08:30:00.000',
          },
        ],
        runs: [
          {
            id: 'run-1',
            task_id: 'task-1',
            trigger_type: 'manual',
            status: 'succeeded',
            conversation_id: 'conv-run-1',
            started_at: '2026-03-11T08:30:00.000',
            finished_at: '2026-03-11T08:31:00.000',
            error_message: null,
          },
        ],
        draft: null,
        activeTab: 'runs',
        isLoading: false,
        isSaving: false,
        error: null,
        canCreateDraft: true,
      },
    })

    expect(wrapper.text()).toContain('Peets Daily Inspection')
  })

  test('uses shared classes for header buttons and segmented tabs', () => {
    const wrapper = mount(TaskDrawer, {
      props: {
        visible: true,
        tasks: [],
        runs: [],
        draft: null,
        activeTab: 'tasks',
        isLoading: false,
        isSaving: false,
        error: null,
        canCreateDraft: true,
      },
    })

    expect(wrapper.get('.task-tabs').classes()).toContain('ui-segmented-tabs')

    const tabs = wrapper.findAll('.task-tab')
    expect(tabs[0]?.classes()).toContain('ui-segmented-tab')
    expect(tabs[1]?.classes()).toContain('ui-segmented-tab')

    const headButtons = wrapper.findAll('.task-head-btn')
    expect(headButtons[0]?.classes()).toContain('ui-pill-btn')
    expect(headButtons[1]?.classes()).toContain('ui-pill-btn')
    expect(headButtons[2]?.classes()).toContain('ui-pill-btn')
  })
})

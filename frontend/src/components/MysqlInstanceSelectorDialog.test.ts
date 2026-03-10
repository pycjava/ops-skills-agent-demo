import { mount } from '@vue/test-utils'
import MysqlInstanceSelectorDialog from './MysqlInstanceSelectorDialog.vue'

describe('MysqlInstanceSelectorDialog', () => {
  test('renders candidates and emits the selected instance', async () => {
    const candidates = [
      {
        instance_id: 'mysql-1',
        instance_name: 'peets-prod-pos-mysql',
        project_key: 'peets-pos',
        region: 'cn-shanghai',
        environment: 'prod',
        credential_ref: 'volc-peets',
        credential_status: 'configured',
        source: 'instance_override',
      },
      {
        instance_id: 'mysql-2',
        instance_name: 'peets-prod-member-mysql',
        project_key: 'peets-member',
        region: 'cn-beijing',
        environment: 'prod',
        credential_ref: 'volc-member',
        credential_status: 'configured',
        source: 'project_binding',
      },
    ]

    const wrapper = mount(MysqlInstanceSelectorDialog, {
      props: {
        visible: true,
        candidates,
        pendingMessage: '帮我巡检 mysql',
      },
    })

    expect(wrapper.text()).toContain('选择要巡检的 MySQL')
    expect(wrapper.text()).toContain('peets-prod-pos-mysql')
    expect(wrapper.text()).toContain('peets-prod-member-mysql')

    await wrapper.get('[data-testid="candidate-radio-mysql-2"]').setValue()
    await wrapper.get('[data-testid="confirm-selection-btn"]').trigger('click')

    const emitted = wrapper.emitted('select')
    expect(emitted).toHaveLength(1)
    expect(emitted?.[0]?.[0]).toMatchObject({
      instance_id: 'mysql-2',
      instance_name: 'peets-prod-member-mysql',
    })
  })
})

import { flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { defineComponent } from 'vue'
import { createMemoryHistory } from 'vue-router'

import { createAppRouter } from './router'


const chatStoreMock = {
  authEnabled: false,
  isAuthenticated: false,
  fetchAuthStatus: vi.fn(async () => {}),
}

vi.mock('./stores/chat', () => ({
  useChatStore: () => chatStoreMock,
}))

vi.mock('./App.vue', () => ({
  default: defineComponent({
    name: 'WorkspaceAppStub',
    template: '<div>workspace</div>',
  }),
}))

vi.mock('./views/LoginPage.vue', () => ({
  default: defineComponent({
    name: 'LoginPageStub',
    template: '<div>login</div>',
  }),
}))


describe('createAppRouter', () => {
  beforeEach(() => {
    chatStoreMock.authEnabled = false
    chatStoreMock.isAuthenticated = false
    chatStoreMock.fetchAuthStatus.mockClear()
  })

  test('redirects unauthenticated users from workspace to /login', async () => {
    chatStoreMock.authEnabled = true
    chatStoreMock.isAuthenticated = false

    const pinia = createPinia()
    const router = createAppRouter(pinia, createMemoryHistory())

    await router.push('/')
    await flushPromises()

    expect(chatStoreMock.fetchAuthStatus).toHaveBeenCalled()
    expect(router.currentRoute.value.fullPath).toBe('/login?next=/')
  })

  test('redirects authenticated users away from /login to next', async () => {
    chatStoreMock.authEnabled = true
    chatStoreMock.isAuthenticated = true

    const pinia = createPinia()
    const router = createAppRouter(pinia, createMemoryHistory())

    await router.push('/login?next=%2F%3Ftab%3Dtasks')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/?tab=tasks')
  })
})

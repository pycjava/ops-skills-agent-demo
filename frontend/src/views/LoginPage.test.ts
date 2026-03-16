import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

import LoginPage from './LoginPage.vue'


const chatStoreMock = {
  authEnabled: true,
  isAuthenticated: false,
  passwordLoginEnabled: true,
  oidcLoginEnabled: true,
  authError: null as string | null,
  isAuthLoading: false,
  login: vi.fn(),
  loginWithPassword: vi.fn(async () => '/workspace'),
}

vi.mock('../stores/chat', () => ({
  useChatStore: () => chatStoreMock,
}))


describe('LoginPage', () => {
  beforeEach(() => {
    chatStoreMock.authEnabled = true
    chatStoreMock.isAuthenticated = false
    chatStoreMock.passwordLoginEnabled = true
    chatStoreMock.oidcLoginEnabled = true
    chatStoreMock.authError = null
    chatStoreMock.isAuthLoading = false
    chatStoreMock.login.mockClear()
    chatStoreMock.loginWithPassword.mockClear()
  })

  test('submits local username and password using the next query string', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/login', component: LoginPage },
        { path: '/workspace', component: { template: '<div>workspace</div>' } },
      ],
    })
    router.push('/login?next=%2Fworkspace')
    await router.isReady()

    const wrapper = mount(LoginPage, {
      global: {
        plugins: [router],
      },
    })

    await wrapper.get('input[name="username"]').setValue('admin')
    await wrapper.get('input[name="password"]').setValue('password-123')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(chatStoreMock.loginWithPassword).toHaveBeenCalledWith({
      username: 'admin',
      password: 'password-123',
      nextPath: '/workspace',
    })
  })

  test('uses the SSO login entry with the next query string', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/login', component: LoginPage },
        { path: '/workspace', component: { template: '<div>workspace</div>' } },
      ],
    })
    router.push('/login?next=%2Fworkspace')
    await router.isReady()

    const wrapper = mount(LoginPage, {
      global: {
        plugins: [router],
      },
    })

    await wrapper.get('[data-testid="login-sso-btn"]').trigger('click')

    expect(chatStoreMock.login).toHaveBeenCalledWith('/workspace')
  })
})

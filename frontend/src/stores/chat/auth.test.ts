import { ref } from 'vue'

import { createAuthDomain } from './auth'
import type { AuthUser } from './types'


function createUser(overrides: Partial<AuthUser> = {}): AuthUser {
  return {
    id: 'user-1',
    subject: 'oidc-user-1',
    email: 'operator@example.com',
    display_name: 'Operator User',
    roles: ['operator'],
    permissions: ['conversations:read', 'conversations:write'],
    ...overrides,
  }
}


describe('createAuthDomain', () => {
  test('fetchAuthStatus stores the backend auth payload and sends cookies', async () => {
    const authEnabled = ref(false)
    const isAuthenticated = ref(false)
    const authUser = ref<AuthUser | null>(null)
    const authPermissions = ref<string[]>([])
    const availablePermissions = ref<string[]>([])
    const loginUrl = ref('/api/auth/login')
    const logoutUrl = ref('/api/auth/logout')
    const oidcLoginEnabled = ref(false)
    const passwordLoginEnabled = ref(false)
    const loginMethods = ref<string[]>([])
    const authError = ref<string | null>(null)
    const isAuthLoading = ref(false)

    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => ({
      ok: true,
      json: async () => ({
        auth_enabled: true,
        authenticated: true,
        user: createUser(),
        permissions: ['conversations:read', 'conversations:write'],
        available_permissions: ['conversations:read', 'conversations:write', 'mcp_servers:read'],
        oidc_login_enabled: true,
        password_login_enabled: true,
        login_methods: ['oidc', 'password'],
        login_url: '/api/auth/login',
        logout_url: '/api/auth/logout',
      }),
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      init,
    }))

    vi.stubGlobal('fetch', fetchMock)

    const domain = createAuthDomain({
      backendUrl: 'http://localhost:8000',
      authEnabled,
      isAuthenticated,
      authUser,
      authPermissions,
      availablePermissions,
      loginUrl,
      logoutUrl,
      oidcLoginEnabled,
      passwordLoginEnabled,
      loginMethods,
      authError,
      isAuthLoading,
    })

    await domain.fetchAuthStatus()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/auth/me',
      expect.objectContaining({
        credentials: 'include',
      }),
    )
    expect(authEnabled.value).toBe(true)
    expect(isAuthenticated.value).toBe(true)
    expect(authUser.value).toEqual(createUser())
    expect(authPermissions.value).toEqual(['conversations:read', 'conversations:write'])
    expect(availablePermissions.value).toContain('mcp_servers:read')
    expect(oidcLoginEnabled.value).toBe(true)
    expect(passwordLoginEnabled.value).toBe(true)
    expect(loginMethods.value).toEqual(['oidc', 'password'])
    expect(authError.value).toBeNull()
    expect(isAuthLoading.value).toBe(false)
  })

  test('hasPermission allows everything when auth is disabled and enforces grants when enabled', () => {
    const domain = createAuthDomain({
      backendUrl: '',
      authEnabled: ref(false),
      isAuthenticated: ref(false),
      authUser: ref<AuthUser | null>(null),
      authPermissions: ref<string[]>(['conversations:read']),
      availablePermissions: ref<string[]>([]),
      loginUrl: ref('/api/auth/login'),
      logoutUrl: ref('/api/auth/logout'),
      oidcLoginEnabled: ref(false),
      passwordLoginEnabled: ref(false),
      loginMethods: ref<string[]>([]),
      authError: ref<string | null>(null),
      isAuthLoading: ref(false),
    })

    expect(domain.hasPermission('inspection_tasks:trigger')).toBe(true)

    domain.authEnabled.value = true
    expect(domain.hasPermission('conversations:read')).toBe(true)
    expect(domain.hasPermission('conversations:write')).toBe(false)
  })

  test('loginWithPassword posts credentials and stores the returned auth payload', async () => {
    const authEnabled = ref(false)
    const isAuthenticated = ref(false)
    const authUser = ref<AuthUser | null>(null)
    const authPermissions = ref<string[]>([])
    const availablePermissions = ref<string[]>([])
    const loginUrl = ref('/api/auth/login')
    const logoutUrl = ref('/api/auth/logout')
    const oidcLoginEnabled = ref(false)
    const passwordLoginEnabled = ref(false)
    const loginMethods = ref<string[]>([])
    const authError = ref<string | null>(null)
    const isAuthLoading = ref(false)

    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => ({
      ok: true,
      json: async () => ({
        auth_enabled: true,
        authenticated: true,
        user: createUser({
          subject: 'local:admin',
          display_name: 'Platform Admin',
          roles: ['admin'],
          permissions: ['cloud_credentials:write'],
        }),
        permissions: ['cloud_credentials:write'],
        available_permissions: ['cloud_credentials:write'],
        oidc_login_enabled: true,
        password_login_enabled: true,
        login_methods: ['oidc', 'password'],
        login_url: '/api/auth/login',
        logout_url: '/api/auth/logout',
        redirect_to: '/workspace',
      }),
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
    }))

    vi.stubGlobal('fetch', fetchMock)

    const domain = createAuthDomain({
      backendUrl: 'http://localhost:8000',
      authEnabled,
      isAuthenticated,
      authUser,
      authPermissions,
      availablePermissions,
      loginUrl,
      logoutUrl,
      oidcLoginEnabled,
      passwordLoginEnabled,
      loginMethods,
      authError,
      isAuthLoading,
    })

    const redirectTo = await domain.loginWithPassword({
      username: 'admin',
      password: 'password-123',
      nextPath: '/workspace',
    })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/auth/login/password',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: 'admin',
          password: 'password-123',
          next: '/workspace',
        }),
      }),
    )
    expect(redirectTo).toBe('/workspace')
    expect(authUser.value?.subject).toBe('local:admin')
    expect(authPermissions.value).toEqual(['cloud_credentials:write'])
    expect(passwordLoginEnabled.value).toBe(true)
  })
})

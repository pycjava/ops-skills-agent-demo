import type { Ref } from 'vue'

import { apiFetch, readErrorMessage } from './helpers'
import type { AuthStatusResponse, AuthUser } from './types'


interface AuthDomainDeps {
  backendUrl: string
  authEnabled: Ref<boolean>
  isAuthenticated: Ref<boolean>
  authUser: Ref<AuthUser | null>
  authPermissions: Ref<string[]>
  availablePermissions: Ref<string[]>
  loginUrl: Ref<string>
  logoutUrl: Ref<string>
  oidcLoginEnabled: Ref<boolean>
  passwordLoginEnabled: Ref<boolean>
  loginMethods: Ref<string[]>
  authError: Ref<string | null>
  isAuthLoading: Ref<boolean>
}


function resolveBackendPath(backendUrl: string, path: string): string {
  if (!path) return backendUrl || '/'
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path
  }
  return `${backendUrl}${path}`
}


export function createAuthDomain({
  backendUrl,
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
}: AuthDomainDeps) {
  function applyAuthPayload(payload: AuthStatusResponse) {
    authEnabled.value = payload.auth_enabled
    isAuthenticated.value = payload.authenticated
    authUser.value = payload.user
    authPermissions.value = payload.permissions || []
    availablePermissions.value = payload.available_permissions || []
    loginUrl.value = payload.login_url || '/api/auth/login'
    logoutUrl.value = payload.logout_url || '/api/auth/logout'
    oidcLoginEnabled.value = payload.oidc_login_enabled || false
    passwordLoginEnabled.value = payload.password_login_enabled || false
    loginMethods.value = payload.login_methods || []
  }

  async function fetchAuthStatus() {
    isAuthLoading.value = true
    authError.value = null

    try {
      const res = await apiFetch(`${backendUrl}/api/auth/me`)
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
      }

      const payload = (await res.json()) as AuthStatusResponse
      applyAuthPayload(payload)
    } catch (error) {
      authEnabled.value = false
      isAuthenticated.value = false
      authUser.value = null
      authPermissions.value = []
      availablePermissions.value = []
      oidcLoginEnabled.value = false
      passwordLoginEnabled.value = false
      loginMethods.value = []
      authError.value = error instanceof Error ? error.message : 'Failed to load auth state.'
    } finally {
      isAuthLoading.value = false
    }
  }

  function hasPermission(permission: string): boolean {
    if (!authEnabled.value) {
      return true
    }
    return authPermissions.value.includes(permission)
  }

  function login(nextPath?: string) {
    const target =
      nextPath ||
      `${window.location.pathname}${window.location.search}${window.location.hash}`
    window.location.assign(
      `${resolveBackendPath(backendUrl, loginUrl.value)}?next=${encodeURIComponent(target)}`,
    )
  }

  async function loginWithPassword({
    username,
    password,
    nextPath = '/',
  }: {
    username: string
    password: string
    nextPath?: string
  }): Promise<string> {
    isAuthLoading.value = true
    authError.value = null

    try {
      const res = await apiFetch(`${backendUrl}/api/auth/login/password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username,
          password,
          next: nextPath,
        }),
      })

      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `HTTP ${res.status}`))
      }

      const payload = (await res.json()) as AuthStatusResponse
      applyAuthPayload(payload)
      return payload.redirect_to || nextPath || '/'
    } catch (error) {
      isAuthenticated.value = false
      authUser.value = null
      authPermissions.value = []
      authError.value = error instanceof Error ? error.message : 'Password login failed.'
      throw error
    } finally {
      isAuthLoading.value = false
    }
  }

  function logout(nextPath = '/') {
    window.location.assign(
      `${resolveBackendPath(backendUrl, logoutUrl.value)}?next=${encodeURIComponent(nextPath)}`,
    )
  }

  return {
    authEnabled,
    isAuthenticated,
    authUser,
    authPermissions,
    availablePermissions,
    loginUrl,
    logoutUrl,
    authError,
    isAuthLoading,
    fetchAuthStatus,
    hasPermission,
    login,
    loginWithPassword,
    logout,
  }
}

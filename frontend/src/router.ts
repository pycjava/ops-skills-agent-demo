import type { Pinia } from 'pinia'
import {
  createRouter,
  createWebHistory,
  type RouterHistory,
} from 'vue-router'

import App from './App.vue'
import LoginPage from './views/LoginPage.vue'
import { useChatStore } from './stores/chat'


function sanitizeNextPath(candidate: unknown): string {
  if (typeof candidate !== 'string') {
    return '/'
  }

  const nextPath = candidate.trim()
  if (!nextPath.startsWith('/') || nextPath.startsWith('//')) {
    return '/'
  }
  return nextPath || '/'
}


export function createAppRouter(
  pinia: Pinia,
  history: RouterHistory = createWebHistory(),
) {
  const router = createRouter({
    history,
    routes: [
      {
        path: '/login',
        name: 'login',
        component: LoginPage,
      },
      {
        path: '/:pathMatch(.*)*',
        name: 'workspace',
        component: App,
      },
    ],
  })

  router.beforeEach(async (to) => {
    const chatStore = useChatStore(pinia)
    await chatStore.fetchAuthStatus()

    if (!chatStore.authEnabled) {
      if (to.name === 'login') {
        return sanitizeNextPath(to.query.next)
      }
      return true
    }

    if (!chatStore.isAuthenticated && to.name !== 'login') {
      return {
        path: '/login',
        query: {
          next: to.fullPath || '/',
        },
      }
    }

    if (chatStore.isAuthenticated && to.name === 'login') {
      return sanitizeNextPath(to.query.next)
    }

    return true
  })

  return router
}

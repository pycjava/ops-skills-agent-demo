<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useChatStore } from '../stores/chat'


const chatStore = useChatStore()
const route = useRoute()
const router = useRouter()

const username = ref('')
const password = ref('')
const submitError = ref('')

const nextPath = computed(() => {
  const candidate = route.query.next
  if (typeof candidate !== 'string') {
    return '/'
  }

  return candidate.startsWith('/') && !candidate.startsWith('//') ? candidate : '/'
})

const canUsePasswordLogin = computed(() => chatStore.passwordLoginEnabled)
const canUseOidcLogin = computed(() => chatStore.oidcLoginEnabled)

async function handlePasswordLogin() {
  submitError.value = ''

  try {
    const redirectTo = await chatStore.loginWithPassword({
      username: username.value,
      password: password.value,
      nextPath: nextPath.value,
    })
    await router.push(redirectTo)
  } catch (error) {
    submitError.value =
      error instanceof Error ? error.message : 'Unable to sign in with username and password.'
  }
}

function handleSsoLogin() {
  chatStore.login(nextPath.value)
}
</script>

<template>
  <main class="login-page">
    <section class="login-shell">
      <div class="login-intro">
        <p class="login-kicker">AgentWeave</p>
        <h1>Sign in to your workspace</h1>
        <p class="login-copy">
          Use the local bootstrap administrator account or continue with your configured SSO
          provider.
        </p>
      </div>

      <div class="login-card">
        <form v-if="canUsePasswordLogin" class="login-form" @submit.prevent="handlePasswordLogin">
          <label class="login-field">
            <span>Username</span>
            <input
              v-model="username"
              name="username"
              type="text"
              autocomplete="username"
              placeholder="admin"
            />
          </label>

          <label class="login-field">
            <span>Password</span>
            <input
              v-model="password"
              name="password"
              type="password"
              autocomplete="current-password"
              placeholder="Enter password"
            />
          </label>

          <button class="login-submit" type="submit" :disabled="chatStore.isAuthLoading">
            {{ chatStore.isAuthLoading ? 'Signing In...' : 'Sign In with Password' }}
          </button>
        </form>

        <div v-if="canUsePasswordLogin && canUseOidcLogin" class="login-divider">
          <span>or</span>
        </div>

        <button
          v-if="canUseOidcLogin"
          class="login-sso"
          type="button"
          data-testid="login-sso-btn"
          :disabled="chatStore.isAuthLoading"
          @click="handleSsoLogin"
        >
          Continue with SSO
        </button>

        <p v-if="submitError || chatStore.authError" class="login-error">
          {{ submitError || chatStore.authError }}
        </p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    radial-gradient(circle at top left, rgba(86, 124, 255, 0.16), transparent 34%),
    radial-gradient(circle at bottom right, rgba(20, 184, 166, 0.18), transparent 36%),
    linear-gradient(135deg, #f4f7fb 0%, #e7edf7 100%);
}

.login-shell {
  width: min(960px, 100%);
  display: grid;
  grid-template-columns: minmax(280px, 1.1fr) minmax(320px, 0.9fr);
  gap: 24px;
  align-items: stretch;
}

.login-intro,
.login-card {
  border-radius: 28px;
  padding: 32px;
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(14px);
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.12);
}

.login-kicker {
  margin: 0 0 12px;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #2563eb;
}

.login-intro h1 {
  margin: 0 0 14px;
  font-size: clamp(2rem, 4vw, 3.4rem);
  line-height: 1.02;
  color: #0f172a;
}

.login-copy {
  margin: 0;
  max-width: 34ch;
  font-size: 1rem;
  line-height: 1.7;
  color: #475569;
}

.login-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 18px;
}

.login-form {
  display: grid;
  gap: 16px;
}

.login-field {
  display: grid;
  gap: 8px;
}

.login-field span {
  font-size: 0.9rem;
  font-weight: 600;
  color: #0f172a;
}

.login-field input {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.45);
  border-radius: 16px;
  padding: 14px 16px;
  font-size: 0.98rem;
  color: #0f172a;
  background: rgba(248, 250, 252, 0.92);
}

.login-field input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.14);
}

.login-submit,
.login-sso {
  border: none;
  border-radius: 999px;
  padding: 14px 18px;
  font-size: 0.98rem;
  font-weight: 700;
  cursor: pointer;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    opacity 0.18s ease;
}

.login-submit {
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #0f766e);
  box-shadow: 0 18px 36px rgba(37, 99, 235, 0.24);
}

.login-sso {
  color: #0f172a;
  background: #fff;
  border: 1px solid rgba(148, 163, 184, 0.4);
}

.login-submit:hover,
.login-sso:hover {
  transform: translateY(-1px);
}

.login-submit:disabled,
.login-sso:disabled {
  cursor: not-allowed;
  opacity: 0.64;
  transform: none;
}

.login-divider {
  position: relative;
  text-align: center;
  color: #64748b;
}

.login-divider::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  border-top: 1px solid rgba(148, 163, 184, 0.32);
}

.login-divider span {
  position: relative;
  padding: 0 12px;
  background: rgba(255, 255, 255, 0.86);
}

.login-error {
  margin: 0;
  font-size: 0.92rem;
  color: #b91c1c;
}

@media (max-width: 840px) {
  .login-shell {
    grid-template-columns: 1fr;
  }

  .login-intro,
  .login-card {
    padding: 24px;
  }
}
</style>

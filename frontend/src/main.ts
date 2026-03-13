import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createAppRouter } from './router'

import RootApp from './RootApp.vue'

const pinia = createPinia()
const router = createAppRouter(pinia)
const app = createApp(RootApp)
app.use(pinia)
app.use(router)
app.mount('#app')

import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useNotificationsStore } from './stores/notifications'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

const notifications = useNotificationsStore(pinia)

app.config.errorHandler = (error) => {
  notifications.notifyError(error)
}

window.addEventListener('unhandledrejection', (event) => {
  notifications.notifyError(event.reason)
})

app.mount('#app')

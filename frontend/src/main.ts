import { createApp } from 'vue'
import App from './App.vue'
import { createAppVuetify } from './plugins/vuetify'
import { createAppRouter } from './router'

createApp(App).use(createAppVuetify()).use(createAppRouter()).mount('#app')

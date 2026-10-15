import { createRouter, createWebHistory } from 'vue-router'
import ConfigurationEditor from './views/ConfigurationEditor.vue'
import ConfigurationList from './views/ConfigurationList.vue'

export const routes = [
  { path: '/', name: 'list', component: ConfigurationList },
  { path: '/configurations/new', name: 'new', component: ConfigurationEditor },
  { path: '/configurations/:id', name: 'edit', component: ConfigurationEditor },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export function createAppRouter() {
  return createRouter({ history: createWebHistory(), routes })
}

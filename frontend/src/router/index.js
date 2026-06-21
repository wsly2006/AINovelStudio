import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/HomeView.vue'),
  },
  {
    path: '/stats/tokens',
    name: 'token-stats',
    component: () => import('../views/TokenStats.vue'),
  },
  {
    path: '/projects/:id/workspace',
    component: () => import('../views/WorkspaceView.vue'),
    props: true,
    redirect: (to) => ({ name: 'workspace-content', params: to.params }),
    children: [
      {
        path: 'content',
        name: 'workspace-content',
        component: () => import('../views/WorkspaceContent.vue'),
      },
      {
        path: 'characters',
        name: 'workspace-characters',
        component: () => import('../views/WorkspaceCharacters.vue'),
      },
      {
        path: 'items',
        name: 'workspace-items',
        component: () => import('../views/WorkspaceItems.vue'),
      },
      {
        path: 'relations',
        name: 'workspace-relations',
        component: () => import('../views/WorkspaceRelations.vue'),
      },
      {
        path: 'plot',
        name: 'workspace-plot',
        component: () => import('../views/WorkspacePlot.vue'),
      },
      {
        path: 'threads',
        name: 'workspace-threads',
        component: () => import('../views/WorkspaceThreads.vue'),
      },
      {
        path: 'world',
        name: 'workspace-world',
        component: () => import('../views/WorkspaceWorld.vue'),
      },
      {
        path: 'progression',
        name: 'workspace-progression',
        component: () => import('../views/WorkspaceLadders.vue'),
      },
      {
        path: 'tasks',
        name: 'workspace-tasks',
        component: () => import('../views/WorkspaceTasks.vue'),
      },
      {
        path: 'publish',
        name: 'workspace-publish',
        component: () => import('../views/WorkspacePublish.vue'),
      },
    ],
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})

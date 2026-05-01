import { createRouter, createWebHistory } from 'vue-router'
import ApprovalsView from '../views/ApprovalsView.vue'
import BudgetEditorView from '../views/BudgetEditorView.vue'
import DashboardsView from '../views/DashboardsView.vue'
import TemplatesView from '../views/TemplatesView.vue'
import VersionAnalysisView from '../views/VersionAnalysisView.vue'
import WorkbenchView from '../views/WorkbenchView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: WorkbenchView },
    { path: '/budget-editor', component: BudgetEditorView },
    { path: '/approvals', component: ApprovalsView },
    { path: '/dashboards', component: DashboardsView },
    { path: '/templates', component: TemplatesView },
    { path: '/versions', component: VersionAnalysisView },
  ],
})

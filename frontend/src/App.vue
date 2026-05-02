<script setup lang="ts">
import { onMounted } from 'vue'
import {
  BarChart3,
  Bell,
  Building2,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  Database,
  FileSpreadsheet,
  GitBranch,
  LayoutDashboard,
  Search,
  Settings2,
} from 'lucide-vue-next'
import { useWorkbenchStore } from './stores/workbench'

const store = useWorkbenchStore()

const navItems = [
  { label: '工作台', to: '/', icon: LayoutDashboard },
  { label: '预算编制', to: '/budget-editor', icon: FileSpreadsheet },
  { label: '审批中心', to: '/approvals', icon: CheckCircle2 },
  { label: '通知中心', to: '/notifications', icon: Bell },
  { label: '预算看板', to: '/dashboards', icon: BarChart3 },
  { label: '主数据', to: '/masterdata', icon: Database },
  { label: '模板管理', to: '/templates', icon: Settings2 },
  { label: '版本分析', to: '/versions', icon: GitBranch },
]

onMounted(() => {
  store.loadMe()
})
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">
          <Building2 :size="20" stroke-width="2" />
        </div>
        <div>
          <strong>研发预算</strong>
          <span>Budget OS</span>
        </div>
      </div>

      <nav class="nav-list" aria-label="主导航">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="nav-link">
          <component :is="item.icon" :size="18" stroke-width="1.9" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <ClipboardList :size="18" />
        <div>
          <strong>2027 年度预算</strong>
          <span>编制中 · 18 个部门</span>
        </div>
      </div>
    </aside>

    <main class="main-panel">
      <header class="topbar">
        <div class="search-box">
          <Search :size="18" stroke-width="2" />
          <input placeholder="搜索预算条目、项目、部门" />
        </div>

        <div class="topbar-actions">
          <button class="context-pill" type="button">
            最新 Approved
            <ChevronDown :size="16" />
          </button>
          <div v-if="!store.currentUser" class="login-box">
            <input v-model="store.loginForm.username" placeholder="用户名" />
            <input v-model="store.loginForm.password" type="password" placeholder="密码" />
            <button class="secondary-button" type="button" :disabled="store.actionLoading" @click="store.login">登录</button>
          </div>
          <div v-else class="user-box">
            <span>{{ store.currentUser.display_name || store.currentUser.username }}</span>
            <button class="secondary-button" type="button" :disabled="store.actionLoading" @click="store.logout">退出</button>
          </div>
          <RouterLink class="icon-button notification-button" to="/notifications" aria-label="通知">
            <Bell :size="18" />
            <span v-if="store.notificationSummary.unread_count" class="notification-dot">
              {{ store.notificationSummary.unread_count > 99 ? '99+' : store.notificationSummary.unread_count }}
            </span>
          </RouterLink>
        </div>
      </header>

      <RouterView />
    </main>
  </div>
</template>

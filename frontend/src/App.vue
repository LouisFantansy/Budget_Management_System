<script setup lang="ts">
import {
  BarChart3,
  Bell,
  Building2,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  FileSpreadsheet,
  GitBranch,
  LayoutDashboard,
  Search,
  Settings2,
} from 'lucide-vue-next'

const navItems = [
  { label: '工作台', to: '/', icon: LayoutDashboard },
  { label: '预算编制', to: '/budget-editor', icon: FileSpreadsheet },
  { label: '审批中心', to: '/approvals', icon: CheckCircle2 },
  { label: '预算看板', to: '/dashboards', icon: BarChart3 },
  { label: '模板管理', to: '/templates', icon: Settings2 },
  { label: '版本分析', to: '/versions', icon: GitBranch },
]
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
          <button class="icon-button" type="button" aria-label="通知">
            <Bell :size="18" />
          </button>
        </div>
      </header>

      <RouterView />
    </main>
  </div>
</template>

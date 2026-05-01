<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { BarChart3, BookmarkPlus, PieChart, TrendingUp } from 'lucide-vue-next'
import { useWorkbenchStore } from '../stores/workbench'

const store = useWorkbenchStore()

const maxMonthlyAmount = computed(() => {
  const amounts = store.budgetOverview?.monthly.map((item) => Number(item.amount)) ?? []
  return Math.max(...amounts, 1)
})

const totalAmount = computed(() => Number(store.budgetOverview?.total_amount ?? 0))

function formatMoney(value: string | number) {
  const amount = Number(value)
  if (amount >= 1_000_000) return `¥ ${(amount / 1_000_000).toFixed(1)}M`
  if (amount >= 1_000) return `¥ ${(amount / 1_000).toFixed(1)}K`
  return `¥ ${amount.toFixed(0)}`
}

function ratio(value: string | number) {
  if (!totalAmount.value) return '0%'
  return `${Math.round((Number(value) / totalAmount.value) * 100)}%`
}

function barHeight(value: string | number) {
  return `${Math.max(8, (Number(value) / maxMonthlyAmount.value) * 100)}%`
}

const departmentOptions = computed(() =>
  store.departments.filter((item) => item.level === 'primary' || item.level === 'secondary' || item.level === 'ss_public'),
)

onMounted(() => {
  Promise.all([store.loadDashboardConfigs(), store.loadBudgetOverview()])
})
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">{{ store.versionContext === 'current_draft' ? 'Current Draft' : 'Latest Approved' }}</p>
      <h1>预算看板</h1>
    </div>
    <div class="button-group">
      <button
        class="context-pill"
        type="button"
        :class="{ active: store.versionContext === 'latest_approved' }"
        :disabled="store.loading"
        @click="store.loadBudgetOverview('latest_approved')"
      >
        Latest Approved
      </button>
      <button
        class="context-pill"
        type="button"
        :class="{ active: store.versionContext === 'current_draft' }"
        :disabled="store.loading"
        @click="store.loadBudgetOverview('current_draft')"
      >
        Current Draft
      </button>
      <select v-model="store.dashboardFocusDepartmentId" class="dashboard-filter" :disabled="store.loading" @change="store.loadBudgetOverview(store.versionContext)">
        <option value="">全部可见部门</option>
        <option v-for="department in departmentOptions" :key="department.id" :value="department.id">{{ department.name }}</option>
      </select>
    </div>
  </section>

  <p v-if="store.error" class="error-banner">{{ store.error }}</p>

  <section class="content-grid">
    <article class="panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Saved Views</p>
          <h2>看板配置</h2>
        </div>
        <BookmarkPlus :size="18" />
      </div>
      <div class="approval-stack">
        <button
          v-for="config in store.dashboardConfigs"
          :key="config.id"
          class="dashboard-config-card"
          type="button"
          :class="{ active: store.activeDashboardConfigId === config.id }"
          :disabled="store.loading"
          @click="store.applyDashboardConfig(config.id)"
        >
          <strong>{{ config.name }}</strong>
          <span>{{ config.scope }} · {{ config.version_context === 'current_draft' ? 'Draft' : 'Approved' }}</span>
          <p>{{ config.department_name || '个人视图' }}<template v-if="config.is_default"> · 默认</template></p>
        </button>
        <p v-if="!store.dashboardConfigs.length" class="empty-note">当前还没有保存的看板配置。</p>
      </div>
    </article>

    <article class="panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Save Current View</p>
          <h2>保存当前看板</h2>
        </div>
        <BookmarkPlus :size="18" />
      </div>
      <div class="field-form dashboard-config-form">
        <input v-model="store.dashboardConfigDraft.name" placeholder="配置名称，如 SS Draft 总览" />
        <select v-model="store.dashboardConfigDraft.scope">
          <option value="personal">个人</option>
          <option value="department">部门共享</option>
          <option value="global">全局共享</option>
        </select>
        <select v-if="store.dashboardConfigDraft.scope === 'department'" v-model="store.dashboardConfigDraft.departmentId">
          <option value="">选择共享部门</option>
          <option v-for="department in departmentOptions" :key="department.id" :value="department.id">{{ department.name }}</option>
        </select>
        <label class="field-required-toggle">
          <input v-model="store.dashboardConfigDraft.isDefault" type="checkbox" />
          设为默认视图
        </label>
        <button class="primary-button" type="button" :disabled="store.actionLoading" @click="store.saveDashboardConfig">
          保存配置
        </button>
      </div>
    </article>
  </section>

  <section class="dashboard-grid">
    <article class="panel chart-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Monthly Planning</p>
          <h2>OPEX by Category</h2>
        </div>
        <BarChart3 :size="18" />
      </div>
      <div class="bar-chart" aria-label="OPEX 月度预算">
        <span
          v-for="item in store.budgetOverview?.monthly ?? []"
          :key="item.month"
          :title="`${item.month}月 ${formatMoney(item.amount)}`"
          :style="{ height: barHeight(item.amount) }"
        ></span>
      </div>
    </article>

    <article class="panel chart-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Project Mix</p>
          <h2>全年项目类别</h2>
        </div>
        <PieChart :size="18" />
      </div>
      <div class="donut-chart"></div>
      <div class="legend-list">
        <span v-for="(item, index) in store.budgetOverview?.by_category.slice(0, 3) ?? []" :key="item.category_id || item.category_name">
          <i :class="index === 0 ? 'legend-blue' : index === 1 ? 'legend-green' : 'legend-amber'"></i>
          {{ item.category_name }} {{ ratio(item.total_amount) }}
        </span>
      </div>
    </article>

    <article class="panel chart-panel full-width">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Department Drilldown</p>
          <h2>By 部门预算</h2>
        </div>
        <TrendingUp :size="18" />
      </div>
      <div class="horizontal-bars">
        <div v-for="item in store.budgetOverview?.by_department ?? []" :key="item.department_id">
          <span>{{ item.department_name }}</span>
          <strong :style="{ width: ratio(item.total_amount) }"></strong>
          <em>{{ formatMoney(item.total_amount) }}</em>
        </div>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { BarChart3, BookmarkPlus, Drill, FolderKanban, Layers3, PieChart, TrendingUp } from 'lucide-vue-next'
import { useWorkbenchStore } from '../stores/workbench'
import type { DashboardDrilldownDimension } from '../types/budget'

const store = useWorkbenchStore()

const maxMonthlyAmount = computed(() => {
  const amounts = store.budgetOverview?.monthly.map((item) => Number(item.amount)) ?? []
  return Math.max(...amounts, 1)
})

const totalAmount = computed(() => Number(store.budgetOverview?.total_amount ?? 0))
const currentExpenseLabel = computed(() => {
  if (store.dashboardExpenseType === 'opex') return 'OPEX'
  if (store.dashboardExpenseType === 'capex') return 'CAPEX'
  return '全部费用类型'
})

const departmentOptions = computed(() =>
  store.departments.filter((item) => item.level === 'primary' || item.level === 'secondary' || item.level === 'ss_public'),
)

const projectHighlights = computed(() => store.budgetOverview?.by_project.slice(0, 4) ?? [])
const projectCategoryHighlights = computed(() => store.budgetOverview?.by_project_category.slice(0, 4) ?? [])
const productLineHighlights = computed(() => store.budgetOverview?.by_product_line.slice(0, 4) ?? [])

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

function applyDimension(dimension: DashboardDrilldownDimension, value: string) {
  void store.loadDashboardDrilldown(dimension, value)
}

function clearDrilldown() {
  store.clearDashboardDrilldown()
}

onMounted(() => {
  Promise.all([store.loadDashboardConfigs(), store.loadBudgetOverview()])
})
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">{{ store.versionContext === 'current_draft' ? 'Current Draft' : 'Latest Approved' }}</p>
      <h1>预算看板</h1>
      <p class="page-note">当前口径：{{ currentExpenseLabel }} · {{ store.dashboardFocusDepartmentId ? '单部门聚焦' : '全部可见部门' }}</p>
    </div>
    <div class="button-group dashboard-toolbar">
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
      <select v-model="store.dashboardExpenseType" class="dashboard-filter" :disabled="store.loading" @change="store.loadBudgetOverview(store.versionContext)">
        <option value="">全部费用类型</option>
        <option value="opex">OPEX</option>
        <option value="capex">CAPEX</option>
      </select>
      <select v-model="store.dashboardFocusDepartmentId" class="dashboard-filter" :disabled="store.loading" @change="store.loadBudgetOverview(store.versionContext)">
        <option value="">全部可见部门</option>
        <option v-for="department in departmentOptions" :key="department.id" :value="department.id">{{ department.name }}</option>
      </select>
    </div>
  </section>

  <p v-if="store.error" class="error-banner">{{ store.error }}</p>

  <section class="dashboard-kpi-grid">
    <article class="panel stat-card">
      <span>预算条目数</span>
      <strong>{{ store.budgetOverview?.line_count ?? 0 }}</strong>
      <p>当前版本口径下的可见预算条目</p>
    </article>
    <article class="panel stat-card tone-green">
      <span>预算总额</span>
      <strong>{{ formatMoney(store.budgetOverview?.total_amount ?? 0) }}</strong>
      <p>{{ store.budgetOverview?.version_context === 'current_draft' ? 'Draft 视角' : 'Approved 视角' }}</p>
    </article>
    <article class="panel stat-card tone-amber">
      <span>项目维度</span>
      <strong>{{ store.budgetOverview?.by_project.length ?? 0 }}</strong>
      <p>项目 / 项目类别 / 产品线已可下钻</p>
    </article>
    <article class="panel stat-card tone-red">
      <span>费用类型</span>
      <strong>{{ currentExpenseLabel }}</strong>
      <p>支持在 OPEX / CAPEX 之间切换</p>
    </article>
  </section>

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
          <p>
            {{ config.department_name || '个人视图' }}
            <template v-if="config.config.expense_type"> · {{ config.config.expense_type.toUpperCase() }}</template>
            <template v-if="config.is_default"> · 默认</template>
          </p>
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
        <input v-model="store.dashboardConfigDraft.name" placeholder="配置名称，如 SS Draft OPEX 总览" />
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
          <h2>月度预算分布</h2>
        </div>
        <BarChart3 :size="18" />
      </div>
      <div class="bar-chart" aria-label="月度预算">
        <button
          v-for="item in store.budgetOverview?.monthly ?? []"
          :key="item.month"
          class="bar-chart-button"
          type="button"
          :title="`${item.month}月 ${formatMoney(item.amount)}`"
          @click="applyDimension('month', String(item.month))"
        >
          <span :style="{ height: barHeight(item.amount) }"></span>
          <em>{{ item.month }}</em>
        </button>
      </div>
    </article>

    <article class="panel chart-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Expense Mix</p>
          <h2>费用类型视角</h2>
        </div>
        <PieChart :size="18" />
      </div>
      <div class="legend-list dashboard-click-list">
        <button
          v-for="item in store.budgetOverview?.by_expense_type ?? []"
          :key="item.expense_type"
          type="button"
          class="legend-chip"
          @click="applyDimension('expense_type', item.expense_type)"
        >
          <i :class="item.expense_type === 'opex' ? 'legend-blue' : 'legend-amber'"></i>
          {{ item.expense_type_label }} {{ ratio(item.total_amount) }}
        </button>
      </div>
      <div class="dashboard-summary-copy">
        <p>从这里切换明细，快速定位 OPEX / CAPEX 的预算条目。</p>
      </div>
    </article>

    <article class="panel chart-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Department Drilldown</p>
          <h2>部门预算</h2>
        </div>
        <TrendingUp :size="18" />
      </div>
      <div class="horizontal-bars">
        <button
          v-for="item in store.budgetOverview?.by_department ?? []"
          :key="item.department_id"
          type="button"
          class="horizontal-bar-button"
          @click="applyDimension('department', item.department_id)"
        >
          <span>{{ item.department_name }}</span>
          <strong :style="{ width: ratio(item.total_amount) }"></strong>
          <em>{{ formatMoney(item.total_amount) }}</em>
        </button>
      </div>
    </article>

    <article class="panel chart-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Category Mix</p>
          <h2>Category 聚合</h2>
        </div>
        <Layers3 :size="18" />
      </div>
      <div class="legend-list dashboard-click-list">
        <button
          v-for="(item, index) in store.budgetOverview?.by_category ?? []"
          :key="item.category_id || item.category_name"
          type="button"
          class="legend-chip"
          @click="applyDimension('category', item.category_id || '__none__')"
        >
          <i :class="index % 3 === 0 ? 'legend-blue' : index % 3 === 1 ? 'legend-green' : 'legend-amber'"></i>
          {{ item.category_name }} {{ ratio(item.total_amount) }}
        </button>
      </div>
    </article>

    <article class="panel chart-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Project Portfolio</p>
          <h2>项目聚合</h2>
        </div>
        <FolderKanban :size="18" />
      </div>
      <div class="dashboard-dimension-list">
        <button v-for="item in projectHighlights" :key="item.project_id || item.project_name" type="button" class="dimension-row" @click="applyDimension('project', item.project_id || '__none__')">
          <span>{{ item.project_name }}</span>
          <strong>{{ formatMoney(item.total_amount) }}</strong>
        </button>
      </div>
    </article>

    <article class="panel chart-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Project Category</p>
          <h2>项目类别</h2>
        </div>
        <PieChart :size="18" />
      </div>
      <div class="dashboard-dimension-list">
        <button
          v-for="item in projectCategoryHighlights"
          :key="item.project_category_id || item.project_category_name"
          type="button"
          class="dimension-row"
          @click="applyDimension('project_category', item.project_category_id || '__none__')"
        >
          <span>{{ item.project_category_name }}</span>
          <strong>{{ formatMoney(item.total_amount) }}</strong>
        </button>
      </div>
    </article>

    <article class="panel chart-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Product Line</p>
          <h2>产品线</h2>
        </div>
        <Layers3 :size="18" />
      </div>
      <div class="dashboard-dimension-list">
        <button
          v-for="item in productLineHighlights"
          :key="item.product_line_id || item.product_line_name"
          type="button"
          class="dimension-row"
          @click="applyDimension('product_line', item.product_line_id || '__none__')"
        >
          <span>{{ item.product_line_name }}</span>
          <strong>{{ formatMoney(item.total_amount) }}</strong>
        </button>
      </div>
    </article>
  </section>

  <section class="panel dashboard-drilldown-panel">
    <div class="panel-title">
      <div>
        <p class="eyebrow">Drilldown</p>
        <h2>预算条目明细</h2>
      </div>
      <Drill :size="18" />
    </div>
    <div v-if="store.dashboardDrilldown" class="dashboard-drilldown-head">
      <div>
        <strong>{{ store.dashboardDrilldown.dimension }}</strong>
        <p>{{ store.dashboardDrilldown.line_count }} 条 · {{ formatMoney(store.dashboardDrilldown.total_amount) }}</p>
      </div>
      <button class="secondary-button" type="button" @click="clearDrilldown">清空</button>
    </div>
    <p v-else class="empty-note">点击上方任一聚合项，即可下钻到预算条目明细。</p>
    <p v-if="store.dashboardDrilldownLoading" class="empty-note">正在加载明细...</p>
    <div v-if="store.dashboardDrilldown?.rows.length" class="data-table dashboard-drilldown-table">
      <div class="table-row table-head dashboard-drilldown-row">
        <span>预算编号</span>
        <span>描述</span>
        <span>部门</span>
        <span>Category</span>
        <span>项目</span>
        <span>项目类别</span>
        <span>产品线</span>
        <span>费用类型</span>
        <span>版本</span>
        <span>金额</span>
      </div>
      <div v-for="row in store.dashboardDrilldown.rows" :key="row.id" class="table-row dashboard-drilldown-row">
        <span>{{ row.budget_no }}</span>
        <span>{{ row.description }}</span>
        <span>{{ row.department_name }}</span>
        <span>{{ row.category_name }}</span>
        <span>{{ row.project_name }}</span>
        <span>{{ row.project_category_name }}</span>
        <span>{{ row.product_line_name }}</span>
        <span>{{ row.expense_type.toUpperCase() }}</span>
        <span>{{ row.version_label }}</span>
        <span>{{ formatMoney(row.total_amount) }}</span>
      </div>
    </div>
  </section>
</template>

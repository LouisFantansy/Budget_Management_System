<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { BarChart3, PieChart, TrendingUp } from 'lucide-vue-next'
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

onMounted(() => {
  store.loadBudgetOverview()
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
    </div>
  </section>

  <p v-if="store.error" class="error-banner">{{ store.error }}</p>

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

<script setup lang="ts">
import { onMounted } from 'vue'
import { ArrowRight, CheckCircle2, Clock3, RefreshCw, ShieldCheck } from 'lucide-vue-next'
import { useWorkbenchStore } from '../stores/workbench'

const store = useWorkbenchStore()

onMounted(() => {
  store.load()
})
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">{{ store.cycleName }}</p>
      <h1>预算工作台</h1>
    </div>
    <button class="primary-button" type="button" :disabled="store.loading || store.actionLoading" @click="store.pullPrimaryConsolidated('opex')">
      {{ store.actionLoading ? '拉取中' : '拉取一级总表' }}
      <RefreshCw :size="17" />
    </button>
  </section>

  <p v-if="store.error" class="error-banner">{{ store.error }}</p>

  <section class="stat-grid" aria-label="预算摘要">
    <article v-for="stat in store.summaryStats" :key="stat.label" class="stat-card" :class="`tone-${stat.tone}`">
      <span>{{ stat.label }}</span>
      <strong>{{ stat.value }}</strong>
      <p>{{ stat.delta }}</p>
    </article>
  </section>

  <section class="content-grid">
    <article class="panel wide-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Department Tasks</p>
          <h2>部门编制状态</h2>
        </div>
        <button class="text-button" type="button">
          查看全部
          <ArrowRight :size="16" />
        </button>
      </div>

      <div class="task-list">
        <div v-for="task in store.tasks" :key="task.department" class="task-row">
          <div>
            <strong>{{ task.department }}</strong>
            <span>{{ task.owner }} · {{ task.version }}</span>
          </div>
          <span class="status-chip">{{ task.status }}</span>
          <strong>{{ task.amount }}</strong>
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Approval</p>
          <h2>待审批</h2>
        </div>
        <Clock3 :size="18" />
      </div>

      <div class="approval-stack">
        <div v-for="item in store.approvals" :key="item.title" class="approval-card">
          <div>
            <strong>{{ item.title }}</strong>
            <span>{{ item.department }} · {{ item.amount }}</span>
          </div>
          <p>{{ item.versionContext === 'submitted_version' ? '送审版本 Dashboard' : 'Draft 整体口径' }} · {{ item.due }}</p>
        </div>
      </div>
    </article>
  </section>

  <section class="panel">
    <div class="panel-title">
      <div>
        <p class="eyebrow">Budget Lines</p>
        <h2>预算条目预览</h2>
      </div>
      <div class="context-badge">
        <ShieldCheck :size="16" />
        默认 Approved
      </div>
    </div>

    <div class="data-table">
      <div class="table-head table-row">
        <span>预算编号</span>
        <span>条目描述</span>
        <span>Category</span>
        <span>项目</span>
        <span>部门</span>
        <span>金额</span>
        <span>来源</span>
      </div>
      <div v-for="line in store.budgetLines" :key="line.budgetNo" class="table-row">
        <span>{{ line.budgetNo }}</span>
        <strong>{{ line.description }}</strong>
        <span>{{ line.category }}</span>
        <span>{{ line.project }}</span>
        <span>{{ line.owner }}</span>
        <strong>{{ line.amount }}</strong>
        <span class="source-pill" :class="{ locked: line.locked }">
          <CheckCircle2 v-if="line.locked" :size="14" />
          {{ line.source }}
        </span>
      </div>
    </div>
  </section>
</template>

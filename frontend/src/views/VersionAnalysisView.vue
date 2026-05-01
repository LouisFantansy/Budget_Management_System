<script setup lang="ts">
import { onMounted } from 'vue'
import { GitBranch, GitCommitHorizontal, GitPullRequestArrow } from 'lucide-vue-next'
import { useWorkbenchStore } from '../stores/workbench'

const store = useWorkbenchStore()

onMounted(() => {
  store.loadVersionDiff()
})
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">Version Graph</p>
      <h1>版本分析</h1>
    </div>
  </section>

  <section class="panel version-panel">
    <div class="version-node approved">
      <GitCommitHorizontal :size="18" />
      <strong>V1 Approved</strong>
      <span>初版</span>
    </div>
    <div class="version-line"></div>
    <div class="version-node approved">
      <GitBranch :size="18" />
      <strong>V2 Approved</strong>
      <span>二级负责人修订</span>
    </div>
    <div class="version-line"></div>
    <div class="version-node draft">
      <GitPullRequestArrow :size="18" />
      <strong>Draft #4</strong>
      <span>送审中 Dashboard</span>
    </div>
  </section>

  <p v-if="store.error" class="error-banner">{{ store.error }}</p>

  <section class="panel">
    <div class="panel-title">
      <div>
        <p class="eyebrow">Diff Summary</p>
        <h2>版本差异</h2>
      </div>
      <span v-if="store.versionDiff" class="status-chip">{{ store.versionDiff.summary.total_changes }} changes</span>
    </div>

    <div v-if="store.versionDiff" class="diff-summary">
      <span>新增 {{ store.versionDiff.summary.added }}</span>
      <span>删除 {{ store.versionDiff.summary.deleted }}</span>
      <span>修改 {{ store.versionDiff.summary.modified }}</span>
    </div>

    <div v-if="store.versionDiff" class="diff-list">
      <div v-for="change in store.versionDiff.changes" :key="`${change.type}-${change.key}`" class="diff-row">
        <span class="status-chip">{{ change.type }}</span>
        <strong>{{ change.budget_no || change.key }}</strong>
        <span>{{ change.description }}</span>
        <em v-if="change.amount_delta">金额变化 {{ change.amount_delta }}</em>
        <em v-if="change.field_changes.length">字段 {{ change.field_changes.length }}</em>
        <em v-if="change.monthly_changes.length">月度 {{ change.monthly_changes.length }}</em>
      </div>
    </div>

    <p v-if="!store.loading && !store.versionDiff" class="empty-note">暂无可比较的修订版本。创建修订 Draft 后会在这里展示差异。</p>
  </section>
</template>

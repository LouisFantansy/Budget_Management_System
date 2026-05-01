<script setup lang="ts">
import { onMounted } from 'vue'
import { CheckCircle2, GitCompareArrows, XCircle } from 'lucide-vue-next'
import { useWorkbenchStore } from '../stores/workbench'

const store = useWorkbenchStore()

onMounted(() => {
  store.load()
})
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">Approval Center</p>
      <h1>审批中心</h1>
    </div>
  </section>

  <p v-if="store.error" class="error-banner">{{ store.error }}</p>

  <section class="content-grid">
    <article v-for="item in store.approvals" :key="item.title" class="panel approval-detail">
      <div class="panel-title">
        <div>
          <p class="eyebrow">{{ item.department }}</p>
          <h2>{{ item.title }}</h2>
        </div>
        <span class="status-chip">{{ item.due }}</span>
      </div>
      <div class="approval-metric">
        <strong>{{ item.amount }}</strong>
        <span>{{ item.versionContext === 'submitted_version' ? '本次送审版本' : '当前 Draft' }}</span>
      </div>
      <div v-if="item.diffSummary" class="diff-summary">
        <span>新增 {{ item.diffSummary.added }}</span>
        <span>删除 {{ item.diffSummary.deleted }}</span>
        <span>修改 {{ item.diffSummary.modified }}</span>
      </div>
      <div class="button-group">
        <button class="secondary-button" type="button">
          <GitCompareArrows :size="17" />
          {{ item.diffSummary ? `${item.diffSummary.total_changes} 项变更` : '查看差异' }}
        </button>
        <button
          class="secondary-button danger"
          type="button"
          :disabled="store.actionLoading || !item.id"
          @click="item.id && store.rejectApproval(item.id)"
        >
          <XCircle :size="17" />
          退回
        </button>
        <button
          class="primary-button"
          type="button"
          :disabled="store.actionLoading || !item.id"
          @click="item.id && store.approveApproval(item.id)"
        >
          <CheckCircle2 :size="17" />
          通过
        </button>
      </div>
    </article>
    <article v-if="!store.loading && !store.approvals.length" class="panel approval-detail">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Empty</p>
          <h2>暂无待审批请求</h2>
        </div>
      </div>
    </article>
  </section>
</template>

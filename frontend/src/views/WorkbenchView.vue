<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, CheckCircle2, Clock3, Download, RefreshCw, ShieldCheck, UploadCloud } from 'lucide-vue-next'
import { useWorkbenchStore } from '../stores/workbench'

const store = useWorkbenchStore()
const router = useRouter()

onMounted(() => {
  store.load()
})

async function openTaskDraft(task: (typeof store.tasks)[number]) {
  const ready = await store.selectDraftContext(task)
  if (!ready) return
  router.push('/budget-editor')
}
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">{{ store.cycleName }}</p>
      <h1>预算工作台</h1>
    </div>
    <div class="button-group">
      <button class="secondary-button" type="button" :disabled="store.loading || store.actionLoading" @click="store.downloadGroupAllocationTemplate">
        <Download :size="17" />
        集团分摊模板
      </button>
      <button class="primary-button" type="button" :disabled="store.loading || store.actionLoading" @click="store.pullPrimaryConsolidated('opex')">
        {{ store.actionLoading ? '拉取中' : '拉取一级总表' }}
        <RefreshCw :size="17" />
      </button>
    </div>
  </section>

  <p v-if="store.error" class="error-banner">{{ store.error }}</p>
  <section v-if="store.primarySyncStatus?.has_updates" class="panel sync-alert-panel">
    <div class="panel-title">
      <div>
        <p class="eyebrow">Primary Sync Alert</p>
        <h2>一级总表有待同步更新</h2>
      </div>
      <div class="context-badge">{{ store.primarySyncStatus.line_count }} 个部门有新 Approved</div>
    </div>
    <p class="empty-note">
      {{ store.primarySyncStatus.departments.map((item) => item.department_name).join('、') }} 已产生新审批版本，建议重新拉取一级总表。
    </p>
  </section>

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
        <div v-for="task in store.tasks" :key="task.bookId ?? task.department" class="task-row">
          <div>
            <strong>{{ task.department }}</strong>
            <span>
              {{ task.owner }} · {{ task.version }}
              <template v-if="task.sourceType === 'primary_consolidated'"> · 一级总表</template>
            </span>
          </div>
          <span class="status-chip">{{ task.status }}</span>
          <div class="task-tail">
            <strong>{{ task.amount }}</strong>
            <button
              v-if="task.currentDraftId"
              class="text-button"
              type="button"
              :disabled="store.actionLoading"
              @click="openTaskDraft(task)"
            >
              进入明细
            </button>
          </div>
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
        <p class="eyebrow">Group Allocation</p>
        <h2>集团分摊导入</h2>
      </div>
      <UploadCloud :size="18" />
    </div>
    <div class="field-form import-toolbar">
      <input v-model="store.allocationDraft.sourceName" placeholder="来源文件名，如 group-allocation.tsv" />
      <button class="primary-button" type="button" :disabled="store.actionLoading" @click="store.importGroupAllocation">
        导入集团分摊
      </button>
    </div>
    <textarea
      v-model="store.allocationDraft.rawText"
      class="import-textarea"
      placeholder="粘贴集团分摊表，至少包含 预算部门 / 预算编号 / 预算条目描述 / 总金额。"
    ></textarea>
    <div v-if="store.latestAllocationUpload" class="import-job-card">
      <strong>最近上传：{{ store.latestAllocationUpload.source_name || '未命名分摊导入' }}</strong>
      <span>
        {{ store.latestAllocationUpload.status }} · 总行数 {{ store.latestAllocationUpload.total_rows }} · 成功
        {{ store.latestAllocationUpload.imported_rows }} · 错误 {{ store.latestAllocationUpload.error_rows }}
      </span>
      <pre v-if="store.latestAllocationUpload.error_rows">{{ JSON.stringify(store.latestAllocationUpload.errors, null, 2) }}</pre>
    </div>
  </section>

  <section class="panel">
    <div class="panel-title">
      <div>
        <p class="eyebrow">Notifications</p>
        <h2>最近通知</h2>
      </div>
      <div class="context-badge">
        <Clock3 :size="16" />
        未读 {{ store.notificationSummary.unread_count }}
      </div>
    </div>
    <div v-if="store.notifications.length" class="notification-list compact">
      <div v-for="item in store.notifications.slice(0, 4)" :key="item.id" class="notification-item" :class="{ unread: item.status === 'unread' }">
        <div class="notification-copy">
          <div class="notification-head">
            <span class="status-chip">{{ item.category === 'approval_todo' ? '审批待办' : item.category === 'approval_result' ? '审批结果' : '系统通知' }}</span>
            <span class="notification-time">{{ new Date(item.created_at).toLocaleString('zh-CN') }}</span>
          </div>
          <strong>{{ item.title }}</strong>
          <p>{{ item.message || '无附加说明' }}</p>
        </div>
      </div>
    </div>
    <p v-else class="empty-note">当前没有通知。</p>
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

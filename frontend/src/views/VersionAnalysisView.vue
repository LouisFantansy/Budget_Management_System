<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { GitBranch, GitCommitHorizontal, GitPullRequestArrow, TrendingUp } from 'lucide-vue-next'
import type { ApiVersionAnalysisVersion, ApiVersionAnalysisHeatmapRow } from '../types/budget'
import { useWorkbenchStore } from '../stores/workbench'

const store = useWorkbenchStore()

onMounted(() => {
  store.loadVersionDiff()
})

const analysis = computed(() => store.versionAnalysis)
const books = computed(() => store.budgetBooks)
const selectedBookId = computed(() => store.versionAnalysisBookId)
const selectedTargetVersionId = computed(() => store.versionAnalysisTargetVersionId)
const selectedVersion = computed(() =>
  analysis.value?.versions.find((item) => item.id === selectedTargetVersionId.value) ?? null,
)
const comparableVersions = computed(() => analysis.value?.versions.filter((item) => item.base_version_id) ?? [])

function bookDepartmentName(departmentId: string) {
  return store.departments.find((item) => item.id === departmentId)?.name ?? departmentId
}

function statusTone(version: ApiVersionAnalysisVersion) {
  if (version.is_current_draft) return 'draft'
  if (version.is_latest_approved) return 'approved'
  if (version.status === 'submitted') return 'submitted'
  if (version.status === 'rejected') return 'rejected'
  return 'approved'
}

function versionIcon(version: ApiVersionAnalysisVersion) {
  if (version.status === 'submitted') return GitPullRequestArrow
  if (version.base_version_id) return GitBranch
  return GitCommitHorizontal
}

function formatMoney(value: string | number) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '¥ 0'
  const sign = numeric < 0 ? '-' : '+'
  const absolute = Math.abs(numeric)
  if (absolute >= 1_000_000) return `${sign}¥ ${(absolute / 1_000_000).toFixed(1)}M`
  if (absolute >= 1_000) return `${sign}¥ ${(absolute / 1_000).toFixed(1)}K`
  return `${sign}¥ ${absolute.toFixed(0)}`
}

function heatLevel(cell: { count: number }) {
  if (cell.count >= 3) return 'heat-3'
  if (cell.count >= 2) return 'heat-2'
  if (cell.count >= 1) return 'heat-1'
  return 'heat-0'
}

function loadBook(bookId: string) {
  if (!bookId || bookId === store.versionAnalysisBookId) return
  store.loadVersionAnalysis(bookId)
}

function focusVersion(versionId: string) {
  const version = comparableVersions.value.find((item) => item.id === versionId)
  if (!version?.base_version_id) return
  store.loadVersionAnalysis(store.versionAnalysisBookId, version.id, version.base_version_id)
}

function rowSummary(row: ApiVersionAnalysisHeatmapRow) {
  const topCell = [...row.cells].sort((left, right) => right.count - left.count)[0]
  if (!topCell || topCell.count === 0) return '无改动'
  const version = analysis.value?.versions.find((item) => item.id === topCell.version_id)
  return `${version?.label ?? '版本'} ${topCell.count} 次`
}
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">Version Graph</p>
      <h1>版本分析</h1>
      <p class="empty-note">按预算表查看真实版本链、修订来源、迭代统计和修改热力图。</p>
    </div>
    <div class="button-group version-book-selector">
      <button
        v-for="book in books"
        :key="book.id"
        class="context-pill"
        :class="{ active: selectedBookId === book.id }"
        type="button"
        :disabled="store.loading"
        @click="loadBook(book.id)"
      >
        {{ analysis?.book.id === book.id ? analysis.book.department_name : bookDepartmentName(book.department) }} · {{ book.expense_type.toUpperCase() }}
      </button>
    </div>
  </section>

  <p v-if="store.error" class="error-banner">{{ store.error }}</p>

  <template v-if="analysis">
    <section class="stat-grid" aria-label="版本分析摘要">
      <article class="stat-card tone-blue">
        <span>版本总数</span>
        <strong>{{ analysis.stats.total_versions }}</strong>
        <p>{{ analysis.stats.revision_rounds }} 次修订</p>
      </article>
      <article class="stat-card tone-green">
        <span>已审批版本</span>
        <strong>{{ analysis.stats.approved_versions + analysis.stats.final_versions }}</strong>
        <p>草稿 {{ analysis.stats.draft_versions }} / 送审 {{ analysis.stats.submitted_versions }}</p>
      </article>
      <article class="stat-card tone-amber">
        <span>分支深度</span>
        <strong>{{ analysis.stats.max_depth }}</strong>
        <p>{{ analysis.stats.branch_heads }} 个当前分支头</p>
      </article>
      <article class="stat-card tone-red">
        <span>当前焦点变更</span>
        <strong>{{ analysis.stats.focus_change_count }}</strong>
        <p>{{ formatMoney(analysis.stats.focus_amount_delta) }}</p>
      </article>
    </section>

    <section class="panel version-book-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Book Context</p>
          <h2>{{ analysis.book.department_name }} · {{ analysis.book.expense_type_label }}</h2>
        </div>
        <div class="version-book-meta">
          <span class="status-chip">{{ analysis.book.source_type_label }}</span>
          <span class="status-chip">{{ analysis.book.status_label }}</span>
        </div>
      </div>
      <p class="page-note">
        {{ analysis.book.cycle_name }} · 模板 {{ analysis.book.template_name }} · 当前 Draft
        {{ analysis.book.current_draft_id ? '已存在' : '无' }} · 最新审批
        {{ analysis.book.latest_approved_version_id ? '已存在' : '无' }}
      </p>
    </section>

    <section class="panel version-panel version-panel-real">
      <div v-for="version in analysis.versions" :key="version.id" class="version-column" :style="{ '--depth': String(version.depth) }">
        <div class="version-rail" :class="{ root: !version.base_version_id }"></div>
        <button
          class="version-node"
          :class="[statusTone(version), { active: version.id === selectedTargetVersionId }]"
          type="button"
          :disabled="!version.base_version_id || store.loading"
          @click="focusVersion(version.id)"
        >
          <component :is="versionIcon(version)" :size="18" />
          <strong>{{ version.label }}</strong>
          <span>{{ version.status_label }}</span>
          <em v-if="version.base_version_label">基于 {{ version.base_version_label }}</em>
          <em>条目 {{ version.line_count }} · {{ formatMoney(version.total_amount) }}</em>
          <em v-if="version.change_summary">
            {{ version.change_summary.total_changes }} changes · {{ formatMoney(version.change_amount_delta) }}
          </em>
        </button>
      </div>
    </section>

    <section class="content-grid version-analysis-grid">
      <article class="panel wide-panel">
        <div class="panel-title">
          <div>
            <p class="eyebrow">Heatmap</p>
            <h2>修改热力图</h2>
          </div>
          <div class="context-badge">
            <TrendingUp :size="16" />
            {{ analysis.heatmap.columns.length }} 个可比版本
          </div>
        </div>

        <div v-if="analysis.heatmap.columns.length" class="heatmap-table">
          <div class="heatmap-head">
            <span>维度</span>
            <span v-for="column in analysis.heatmap.columns" :key="column.version_id">
              {{ column.label }}
              <em>{{ column.total_changes }} 次</em>
            </span>
            <span>热点</span>
          </div>
          <div v-for="row in analysis.heatmap.rows" :key="row.key" class="heatmap-row">
            <strong>{{ row.label }}</strong>
            <button
              v-for="cell in row.cells"
              :key="`${row.key}-${cell.version_id}`"
              class="heatmap-cell"
              :class="[heatLevel(cell), { active: cell.version_id === selectedTargetVersionId && cell.count > 0 }]"
              type="button"
              :disabled="cell.count === 0 || store.loading"
              @click="focusVersion(cell.version_id)"
            >
              <span>{{ cell.count }}</span>
              <em>{{ cell.amount_delta === '0.00' ? '无金额变化' : formatMoney(cell.amount_delta) }}</em>
            </button>
            <span class="heatmap-summary">{{ rowSummary(row) }}</span>
          </div>
        </div>

        <p v-else class="empty-note">当前预算表只有单一版本，待创建修订 Draft 后显示热力图。</p>
      </article>

      <article class="panel">
        <div class="panel-title">
          <div>
            <p class="eyebrow">Focus Version</p>
            <h2>{{ selectedVersion?.label ?? '暂无可比版本' }}</h2>
          </div>
          <span v-if="selectedVersion" class="status-chip">{{ selectedVersion.status_label }}</span>
        </div>

        <div v-if="selectedVersion" class="approval-metric">
          <strong>{{ selectedVersion.change_summary?.total_changes ?? 0 }}</strong>
          <span>相对 {{ selectedVersion.base_version_label || '上一个版本' }} 的总变更</span>
        </div>
        <div v-if="selectedVersion" class="detail-meta-list">
          <div>
            <span>修订来源</span>
            <strong>{{ selectedVersion.base_version_label || '首版' }}</strong>
          </div>
          <div>
            <span>金额变化</span>
            <strong>{{ formatMoney(selectedVersion.change_amount_delta) }}</strong>
          </div>
          <div>
            <span>分支深度</span>
            <strong>Level {{ selectedVersion.depth + 1 }}</strong>
          </div>
          <div>
            <span>备注</span>
            <strong>{{ selectedVersion.notes || '无备注' }}</strong>
          </div>
        </div>
        <p v-else class="empty-note">当前预算表暂无可比较版本。</p>
      </article>
    </section>

    <section class="panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Diff Summary</p>
          <h2>版本差异明细</h2>
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
</template>

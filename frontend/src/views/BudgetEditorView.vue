<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Download, GitBranchPlus, LockKeyhole, Plus, Send, UploadCloud } from 'lucide-vue-next'
import { useWorkbenchStore } from '../stores/workbench'

const store = useWorkbenchStore()
const showImportPanel = ref(false)

onMounted(() => {
  if (!store.budgetLines.length) store.load()
  if (!store.masterData.projects.length) store.loadMasterData()
})

function dynamicValue(line: { dynamicData?: Record<string, unknown> }, code: string) {
  const value = line.dynamicData?.[code]
  if (value === undefined || value === null || value === '') return '-'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function isEditable(line: Parameters<typeof store.canEditLine>[0]) {
  return store.canEditLine(line)
}

function fieldError(lineId: string | undefined, code: string) {
  if (!lineId) return ''
  return store.fieldErrors[`${lineId}:${code}`] ?? ''
}

function updateDynamicField(line: Parameters<typeof store.updateDynamicField>[0], field: Parameters<typeof store.updateDynamicField>[1], event: Event) {
  const target = event.target as HTMLInputElement | HTMLSelectElement
  if (field.data_type === 'boolean') {
    store.updateDynamicField(line, field, (target as HTMLInputElement).checked)
    return
  }
  store.updateDynamicField(line, field, target.value)
}

function recommendation(lineId: string | undefined) {
  if (!lineId) return null
  return store.recommendations[lineId]?.[0] ?? null
}

function lineError(lineId: string | undefined) {
  if (!lineId) return ''
  return store.lineErrors[lineId] ?? ''
}

const latestImportSummary = computed(() => store.latestImportJob?.summary.message ?? '')
const isPrimaryConsolidated = computed(() => store.activeSourceType === 'primary_consolidated')
const activeLines = computed(() => store.budgetLines.filter((line) => line.versionId === store.activeDraftVersionId))
const visibleTemplateFields = computed(() => store.templateFields.filter((field) => field.user_permissions?.visible !== false))
const selectedLine = computed(() => activeLines.value.find((line) => line.id === store.selectedLineId) ?? activeLines.value[0] ?? null)
const totalActiveAmount = computed(() =>
  activeLines.value.reduce((sum, line) => sum + Number(line.totalAmount ?? 0), 0).toFixed(2),
)
const editableActiveLines = computed(() => activeLines.value.filter((line) => store.canEditLine(line)))
const allEditableSelected = computed(
  () => !!editableActiveLines.value.length && editableActiveLines.value.every((line) => store.isLineSelected(line.id)),
)

function openLineAction(line: (typeof store.budgetLines)[number]) {
  if (isPrimaryConsolidated.value) {
    store.selectLine(line.id)
    return
  }
  store.renameLine(line)
}

function lineStateLabel(line: (typeof store.budgetLines)[number]) {
  if (isPrimaryConsolidated.value) return '一级可修订'
  return line.editableBySecondary === false ? '二级锁定' : '可编辑'
}

function lineStateLocked(line: (typeof store.budgetLines)[number]) {
  return !isPrimaryConsolidated.value && line.editableBySecondary === false
}

function optionValues(field: (typeof store.templateFields)[number]) {
  return store.resolveOptionValues(field.option_source ?? '').map((item) => item.label)
}

function toggleSelectAll() {
  if (allEditableSelected.value) {
    store.clearLineSelection()
    return
  }
  store.selectAllActiveLines()
}
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">OPEX / CAPEX</p>
      <h1>预算编制表</h1>
    </div>
    <div class="button-group">
      <button class="secondary-button" type="button" :disabled="store.actionLoading" @click="showImportPanel = !showImportPanel">
        <UploadCloud :size="17" />
        Excel 导入
      </button>
      <button class="secondary-button" type="button" :disabled="store.actionLoading" @click="store.exportActiveDraftCsv">
        <Download :size="17" />
        导出 CSV
      </button>
      <button class="secondary-button" type="button" :disabled="store.actionLoading" @click="store.createRevisionDraft">
        <GitBranchPlus :size="17" />
        创建修订
      </button>
      <button class="secondary-button" type="button" :disabled="store.actionLoading" @click="store.submitActiveDraft">
        <Send :size="17" />
        提交送审
      </button>
      <button class="primary-button" type="button" :disabled="store.actionLoading" @click="store.createDraftLine">
        <Plus :size="17" />
        新增条目
      </button>
    </div>
  </section>

  <p v-if="store.error" class="error-banner">{{ store.error }}</p>

  <section class="panel">
    <div class="panel-title">
      <div>
        <p class="eyebrow">Draft Context</p>
        <h2>{{ isPrimaryConsolidated ? '一级总表工作区' : '部门预算工作区' }}</h2>
      </div>
    </div>
    <div class="detail-grid">
      <div class="detail-card">
        <span>当前预算表</span>
        <strong>{{ isPrimaryConsolidated ? 'SS 一级总表' : '部门 Draft' }}</strong>
      </div>
      <div class="detail-card">
        <span>来源类型</span>
        <strong>{{ isPrimaryConsolidated ? '审批版汇总' : '部门自编' }}</strong>
      </div>
      <div class="detail-card">
        <span>当前条目数</span>
        <strong>{{ activeLines.length }}</strong>
      </div>
      <div class="detail-card">
        <span>当前总金额</span>
        <strong>¥ {{ totalActiveAmount }}</strong>
      </div>
    </div>
  </section>

  <section v-if="!isPrimaryConsolidated" class="panel">
    <div class="panel-title">
      <div>
        <p class="eyebrow">Bulk Operations</p>
        <h2>批量维护</h2>
      </div>
      <span class="context-badge">已选 {{ store.selectedLineIds.length }} 条</span>
    </div>
    <div class="bulk-toolbar">
      <button class="secondary-button" type="button" :disabled="store.actionLoading || !editableActiveLines.length" @click="toggleSelectAll">
        {{ allEditableSelected ? '清空全选' : '全选当前 Draft' }}
      </button>
      <button class="secondary-button" type="button" :disabled="store.actionLoading || !store.selectedLineIds.length" @click="store.bulkDuplicateLines">
        批量复制
      </button>
      <button class="secondary-button danger" type="button" :disabled="store.actionLoading || !store.selectedLineIds.length" @click="store.bulkDeleteLines">
        批量删除
      </button>
    </div>
    <div class="field-form bulk-form">
      <input v-model="store.bulkEditDraft.reason" placeholder="统一写入采购原因说明（reason）" />
      <input v-model="store.bulkEditDraft.purchaseReason" placeholder="统一写入采购原因补充（purchase_reason）" />
      <input v-model="store.bulkEditDraft.comment" placeholder="统一写入批量备注" />
      <button class="primary-button" type="button" :disabled="store.actionLoading || !store.selectedLineIds.length" @click="store.bulkPatchLines">
        批量更新
      </button>
    </div>
  </section>

  <section v-if="isPrimaryConsolidated && selectedLine" class="panel">
    <div class="panel-title">
      <div>
        <p class="eyebrow">Line Inspector</p>
        <h2>汇总条目详情</h2>
      </div>
      <span class="context-badge">当前选中 {{ selectedLine.budgetNo }}</span>
    </div>
    <div class="detail-grid">
      <div class="detail-card">
        <span>来源部门</span>
        <strong>{{ selectedLine.sourceDepartmentCode ?? '-' }}</strong>
      </div>
      <div class="detail-card">
        <span>来源预算表</span>
        <strong>{{ String(selectedLine.adminAnnotations?.source_book_id ?? '-') }}</strong>
      </div>
      <div class="detail-card">
        <span>来源版本</span>
        <strong>{{ String(selectedLine.adminAnnotations?.source_version_id ?? '-') }}</strong>
      </div>
      <div class="detail-card">
        <span>来源类型</span>
        <strong>{{ selectedLine.source }}</strong>
      </div>
    </div>
    <div class="detail-columns">
      <article class="detail-section">
        <h3>条目摘要</h3>
        <div class="detail-meta-list">
          <div>
            <span>预算编号</span>
            <strong>{{ selectedLine.budgetNo }}</strong>
          </div>
          <div>
            <span>条目描述</span>
            <strong>{{ selectedLine.description }}</strong>
          </div>
          <div>
            <span>Category</span>
            <strong>{{ selectedLine.category }}</strong>
          </div>
          <div>
            <span>Project</span>
            <strong>{{ selectedLine.project }}</strong>
          </div>
          <div>
            <span>单价</span>
            <strong>{{ selectedLine.unitPrice ?? '0.00' }}</strong>
          </div>
          <div>
            <span>总金额</span>
            <strong>{{ selectedLine.amount }}</strong>
          </div>
        </div>
      </article>
      <article class="detail-section">
        <h3>月度计划</h3>
        <div v-if="selectedLine.monthlyPlans?.length" class="plan-list">
          <div v-for="plan in selectedLine.monthlyPlans" :key="`${selectedLine.id}-${plan.month}`" class="plan-row">
            <span>{{ plan.month }} 月</span>
            <strong>数量 {{ plan.quantity }}</strong>
            <strong>金额 {{ plan.amount }}</strong>
          </div>
        </div>
        <p v-else class="empty-note">当前条目没有月度计划。</p>
      </article>
      <article class="detail-section">
        <h3>动态字段</h3>
        <div v-if="store.templateFields.length" class="detail-meta-list">
          <div v-for="field in visibleTemplateFields" :key="`${selectedLine.id}-${field.id}-detail`">
            <span>{{ field.label }}</span>
            <strong>{{ dynamicValue(selectedLine, field.code) }}</strong>
          </div>
        </div>
        <p v-else class="empty-note">当前模板没有动态字段。</p>
      </article>
    </div>
  </section>

  <section v-if="showImportPanel" class="panel">
    <div class="panel-title">
      <div>
        <p class="eyebrow">Import / Export</p>
        <h2>Excel 粘贴导入</h2>
      </div>
      <UploadCloud :size="18" />
    </div>
    <div class="field-form import-toolbar">
      <input v-model="store.importDraft.sourceName" placeholder="来源文件名，如 budget-import.tsv" />
      <select v-model="store.importDraft.mode">
        <option value="append">追加导入</option>
        <option value="replace">覆盖导入</option>
      </select>
      <button class="secondary-button" type="button" :disabled="store.actionLoading" @click="store.downloadImportTemplate">
        下载导入模板
      </button>
      <button class="secondary-button" type="button" :disabled="store.actionLoading" @click="store.downloadImportSample">
        下载示例数据
      </button>
      <button class="primary-button" type="button" :disabled="store.actionLoading" @click="store.importBudgetLines">
        开始导入
      </button>
    </div>
    <textarea
      v-model="store.importDraft.rawText"
      class="import-textarea"
      placeholder="直接粘贴 Excel 复制出的表格内容，支持制表符 TSV 或 CSV。"
    ></textarea>
    <p v-if="latestImportSummary" class="empty-note">{{ latestImportSummary }}</p>
    <div v-if="store.latestImportJob" class="import-job-card">
      <strong>最近导入：{{ store.latestImportJob.source_name || '未命名导入' }}</strong>
      <span>
        {{ store.latestImportJob.status }} · 总行数 {{ store.latestImportJob.total_rows }} · 成功 {{ store.latestImportJob.imported_rows }} · 错误
        {{ store.latestImportJob.error_rows }}
      </span>
      <button
        v-if="store.latestImportJob.error_rows"
        class="text-button"
        type="button"
        :disabled="store.actionLoading"
        @click="store.loadImportJobErrors(store.latestImportJob.id)"
      >
        查看错误
      </button>
    </div>
    <div v-if="store.importJobErrors?.errors.length" class="import-error-list">
      <div v-for="item in store.importJobErrors.errors" :key="item.row" class="import-error-item">
        <strong>第 {{ item.row }} 行</strong>
        <pre>{{ JSON.stringify(item.errors, null, 2) }}</pre>
      </div>
    </div>
  </section>

  <section class="panel editor-panel">
    <div class="panel-title">
      <div>
        <p class="eyebrow">
          {{ isPrimaryConsolidated ? 'SS · 一级总表 Draft' : '部门 Draft 预算编制' }}
        </p>
        <h2>{{ isPrimaryConsolidated ? '一级总表明细' : '当前修订' }}</h2>
      </div>
      <span class="status-chip">{{ isPrimaryConsolidated ? '汇总视图' : '待送审' }}</span>
    </div>

    <div class="editor-table">
      <div
        class="editor-row editor-head"
        :style="{ '--dynamic-columns': visibleTemplateFields.length, '--source-columns': isPrimaryConsolidated ? 1 : 0, '--selection-columns': isPrimaryConsolidated ? 0 : 1 }"
      >
        <span v-if="!isPrimaryConsolidated">
          <input type="checkbox" :checked="allEditableSelected" :disabled="store.actionLoading || !editableActiveLines.length" @change="toggleSelectAll" />
        </span>
        <span>预算编号</span>
        <span>条目描述</span>
        <span>Category</span>
        <span>Project</span>
        <span v-if="isPrimaryConsolidated">来源部门</span>
        <span>单价</span>
        <span>推荐价</span>
        <span>总数量</span>
        <span>总金额</span>
        <span v-for="field in visibleTemplateFields" :key="field.id">
          {{ field.label }}{{ field.required ? ' *' : '' }}
        </span>
        <span>状态</span>
        <span>操作</span>
      </div>
      <p v-if="!activeLines.length" class="editor-empty">当前 Draft 暂无预算条目。</p>
      <div
        v-for="line in activeLines"
        :key="line.id ?? line.budgetNo"
        class="editor-row"
        :class="{ 'has-row-error': !!lineError(line.id) }"
        :style="{ '--dynamic-columns': visibleTemplateFields.length, '--source-columns': isPrimaryConsolidated ? 1 : 0, '--selection-columns': isPrimaryConsolidated ? 0 : 1 }"
      >
        <span v-if="!isPrimaryConsolidated">
          <input
            type="checkbox"
            :checked="store.isLineSelected(line.id)"
            :disabled="store.actionLoading || !store.canEditLine(line)"
            @change="store.toggleLineSelection(line.id)"
          />
        </span>
        <span>{{ line.budgetNo }}</span>
        <strong>{{ line.description }}</strong>
        <span>{{ line.category }}</span>
        <span>{{ line.project }}</span>
        <span v-if="isPrimaryConsolidated">{{ line.sourceDepartmentCode ?? '-' }}</span>
        <span>{{ line.unitPrice ?? '0.00' }}</span>
        <span class="recommendation-cell">
          <button class="text-button" type="button" :disabled="store.actionLoading" @click="store.loadRecommendations(line)">
            查询
          </button>
          <template v-if="recommendation(line.id)">
            <strong>{{ recommendation(line.id)?.recommended_price }}</strong>
            <button
              class="text-button"
              type="button"
              :disabled="store.actionLoading || !store.canEditLine(line)"
              @click="store.applyRecommendedPrice(line, recommendation(line.id)!.recommended_price)"
            >
              带入
            </button>
          </template>
        </span>
        <span>{{ line.totalQuantity ?? '0.00' }}</span>
        <strong>{{ line.amount }}</strong>
        <span v-for="field in visibleTemplateFields" :key="`${line.id}-${field.id}`" class="dynamic-cell">
          <input
            v-if="isEditable(line) && store.canEditDynamicField(line, field) && field.data_type === 'boolean'"
            class="cell-input-checkbox"
            type="checkbox"
            :checked="dynamicValue(line, field.code) === 'true'"
            :disabled="store.actionLoading"
            @change="updateDynamicField(line, field, $event)"
          />
          <select
            v-else-if="isEditable(line) && store.canEditDynamicField(line, field) && ['select', 'multi_select', 'project', 'department', 'user'].includes(field.input_type)"
            class="cell-input"
            :value="dynamicValue(line, field.code) === '-' ? '' : dynamicValue(line, field.code)"
            :disabled="store.actionLoading"
            @change="updateDynamicField(line, field, $event)"
          >
            <option value="">请选择</option>
            <option v-for="option in optionValues(field)" :key="`${field.id}-${option}`" :value="option">{{ option }}</option>
          </select>
          <input
            v-else-if="isEditable(line) && store.canEditDynamicField(line, field)"
            class="cell-input"
            :type="field.data_type === 'date' ? 'date' : field.data_type === 'number' || field.data_type === 'money' ? 'number' : 'text'"
            :value="dynamicValue(line, field.code) === '-' ? '' : dynamicValue(line, field.code)"
            :disabled="store.actionLoading"
            @change="updateDynamicField(line, field, $event)"
          />
          <template v-else>{{ dynamicValue(line, field.code) }}</template>
          <em v-if="fieldError(line.id, field.code)" class="field-error">{{ fieldError(line.id, field.code) }}</em>
        </span>
        <span class="source-pill" :class="{ locked: lineStateLocked(line) }">
          <LockKeyhole v-if="lineStateLocked(line)" :size="14" />
          {{ lineStateLabel(line) }}
        </span>
        <button
          class="text-button"
          type="button"
          :disabled="store.actionLoading || (!isPrimaryConsolidated && !store.canEditLine(line))"
          @click="openLineAction(line)"
        >
          {{ isPrimaryConsolidated ? '查看条目' : '快速编辑' }}
        </button>
        <em v-if="lineError(line.id)" class="row-error">{{ lineError(line.id) }}</em>
      </div>
    </div>
  </section>
</template>

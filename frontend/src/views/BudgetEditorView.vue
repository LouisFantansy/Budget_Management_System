<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Download, GitBranchPlus, LockKeyhole, Plus, Send, UploadCloud } from 'lucide-vue-next'
import { useWorkbenchStore } from '../stores/workbench'

const store = useWorkbenchStore()
const showImportPanel = ref(false)

onMounted(() => {
  if (!store.budgetLines.length) store.load()
})

function dynamicValue(line: { dynamicData?: Record<string, unknown> }, code: string) {
  const value = line.dynamicData?.[code]
  if (value === undefined || value === null || value === '') return '-'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function isEditable(line: { versionId?: string; locked: boolean }) {
  return !line.locked && line.versionId === store.activeDraftVersionId
}

function fieldError(lineId: string | undefined, code: string) {
  if (!lineId) return ''
  return store.fieldErrors[`${lineId}:${code}`] ?? ''
}

function updateDynamicField(line: Parameters<typeof store.updateDynamicField>[0], field: Parameters<typeof store.updateDynamicField>[1], event: Event) {
  const target = event.target as HTMLInputElement
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
        <p class="eyebrow">平台软件部 · Draft #4</p>
        <h2>当前修订</h2>
      </div>
      <span class="status-chip">待送审</span>
    </div>

    <div class="editor-table">
      <div class="editor-row editor-head" :style="{ '--dynamic-columns': store.templateFields.length }">
        <span>预算编号</span>
        <span>条目描述</span>
        <span>Category</span>
        <span>Project</span>
        <span>单价</span>
        <span>推荐价</span>
        <span>总数量</span>
        <span>总金额</span>
        <span v-for="field in store.templateFields" :key="field.id">
          {{ field.label }}{{ field.required ? ' *' : '' }}
        </span>
        <span>状态</span>
        <span>操作</span>
      </div>
      <div
        v-for="line in store.budgetLines"
        :key="line.budgetNo"
        class="editor-row"
        :class="{ 'has-row-error': !!lineError(line.id) }"
        :style="{ '--dynamic-columns': store.templateFields.length }"
      >
        <span>{{ line.budgetNo }}</span>
        <strong>{{ line.description }}</strong>
        <span>{{ line.category }}</span>
        <span>{{ line.project }}</span>
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
              :disabled="store.actionLoading || line.versionId !== store.activeDraftVersionId"
              @click="store.applyRecommendedPrice(line, recommendation(line.id)!.recommended_price)"
            >
              带入
            </button>
          </template>
        </span>
        <span>12</span>
        <strong>{{ line.amount }}</strong>
        <span v-for="field in store.templateFields" :key="`${line.id}-${field.id}`" class="dynamic-cell">
          <input
            v-if="isEditable(line)"
            class="cell-input"
            :type="field.data_type === 'date' ? 'date' : field.data_type === 'number' || field.data_type === 'money' ? 'number' : 'text'"
            :value="dynamicValue(line, field.code) === '-' ? '' : dynamicValue(line, field.code)"
            :disabled="store.actionLoading"
            @change="updateDynamicField(line, field, $event)"
          />
          <template v-else>{{ dynamicValue(line, field.code) }}</template>
          <em v-if="fieldError(line.id, field.code)" class="field-error">{{ fieldError(line.id, field.code) }}</em>
        </span>
        <span class="source-pill" :class="{ locked: line.locked }">
          <LockKeyhole v-if="line.locked" :size="14" />
          {{ line.locked ? '专题锁定' : '可编辑' }}
        </span>
        <button
          class="text-button"
          type="button"
          :disabled="store.actionLoading || line.versionId !== store.activeDraftVersionId"
          @click="store.renameLine(line)"
        >
          快速编辑
        </button>
        <em v-if="lineError(line.id)" class="row-error">{{ lineError(line.id) }}</em>
      </div>
    </div>
  </section>
</template>

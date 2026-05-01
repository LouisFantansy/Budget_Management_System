<script setup lang="ts">
import { onMounted } from 'vue'
import { GitBranchPlus, LockKeyhole, Plus, Send, UploadCloud } from 'lucide-vue-next'
import { useWorkbenchStore } from '../stores/workbench'

const store = useWorkbenchStore()

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
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">OPEX / CAPEX</p>
      <h1>预算编制表</h1>
    </div>
    <div class="button-group">
      <button class="secondary-button" type="button">
        <UploadCloud :size="17" />
        Excel 导入
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
      </div>
    </div>
  </section>
</template>

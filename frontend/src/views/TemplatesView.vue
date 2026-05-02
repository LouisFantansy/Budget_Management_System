<script setup lang="ts">
import { onMounted } from 'vue'
import { Copy, Eye, FunctionSquare, ListChecks, Plus, Trash2 } from 'lucide-vue-next'
import { useWorkbenchStore } from '../stores/workbench'

const store = useWorkbenchStore()

onMounted(() => {
  store.loadTemplates()
})

function renameField(field: (typeof store.templateFields)[number], event: Event) {
  const target = event.target as HTMLInputElement
  const label = target.value.trim()
  if (label && label !== field.label) {
    store.updateTemplateField(field, { label })
  }
}

function toggleRequired(field: (typeof store.templateFields)[number], event: Event) {
  const target = event.target as HTMLInputElement
  store.updateTemplateField(field, { required: target.checked })
}

function updateFormulaInputType(event: Event) {
  const target = event.target as HTMLSelectElement
  store.templateFieldDraft.inputType = target.value as typeof store.templateFieldDraft.inputType
  if (store.templateFieldDraft.inputType === 'formula' && store.templateFieldDraft.dataType === 'text') {
    store.templateFieldDraft.dataType = 'money'
  }
  if (store.templateFieldDraft.inputType !== 'formula') {
    store.templateFieldDraft.formula = ''
  }
}

function deleteField(field: (typeof store.templateFields)[number]) {
  if (window.confirm(`确认删除字段「${field.label}」？`)) {
    store.deleteTemplateField(field)
  }
}
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">Schema Version 1</p>
      <h1>模板管理</h1>
    </div>
    <button class="primary-button" type="button" :disabled="store.actionLoading" @click="store.createTemplateField">
      <Plus :size="17" />
      新增字段
    </button>
  </section>

  <p v-if="store.error" class="error-banner">{{ store.error }}</p>

  <section class="content-grid">
    <article class="panel wide-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">{{ store.templates[0]?.name ?? 'Template' }}</p>
          <h2>字段配置</h2>
        </div>
        <span class="status-chip">{{ store.templates[0]?.status ?? 'Loading' }}</span>
      </div>
      <div class="field-list">
        <div class="field-form">
          <input v-model="store.templateFieldDraft.code" placeholder="字段编码，如 purchase_reason" />
          <input v-model="store.templateFieldDraft.label" placeholder="显示名称，如 采购原因" />
          <select v-model="store.templateFieldDraft.dataType">
            <option value="text">文本</option>
            <option value="number">数字</option>
            <option value="money">金额</option>
            <option value="date">日期</option>
            <option value="boolean">布尔</option>
            <option value="option">选项</option>
          </select>
          <select :value="store.templateFieldDraft.inputType" @change="updateFormulaInputType">
            <option value="text">普通输入</option>
            <option value="formula">公式字段</option>
          </select>
          <input
            v-if="store.templateFieldDraft.inputType === 'formula'"
            v-model="store.templateFieldDraft.formula"
            placeholder="公式，如 unit_price * total_quantity"
          />
          <label>
            <input v-model="store.templateFieldDraft.required" type="checkbox" />
            必填
          </label>
        </div>
        <div v-for="field in store.templateFields" :key="field.id">
          <ListChecks :size="16" />
          <input class="field-label-input" :value="field.label" :disabled="store.actionLoading" @change="renameField(field, $event)" />
          <em>{{ field.code }} · {{ field.data_type }} · {{ field.input_type === 'formula' ? `公式: ${field.formula}` : field.required ? '必填' : '选填' }}</em>
          <label class="field-required-toggle">
            <input :checked="field.required" type="checkbox" :disabled="store.actionLoading" @change="toggleRequired(field, $event)" />
            必填
          </label>
          <button class="icon-button danger-icon" type="button" :disabled="store.actionLoading" @click="deleteField(field)">
            <Trash2 :size="15" />
          </button>
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Rules</p>
          <h2>公式与权限</h2>
        </div>
        <FunctionSquare :size="18" />
      </div>
      <div class="rule-stack">
        <p>总数量 = 1-12 月数量加总</p>
        <p>总金额 = 1-12 月金额加总</p>
        <p><Eye :size="15" />保密列仅一级预算管理员可见</p>
        <p><Copy :size="15" />Schema Version {{ store.templates[0]?.schema_version ?? '-' }}</p>
      </div>
    </article>
  </section>
</template>

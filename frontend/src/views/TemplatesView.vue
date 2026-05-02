<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Copy, Eye, FunctionSquare, GitBranchPlus, ListChecks, Plus, Settings2, Trash2 } from 'lucide-vue-next'
import { useWorkbenchStore } from '../stores/workbench'

const store = useWorkbenchStore()

const activeTemplate = computed(() => store.templates.find((item) => item.id === store.activeTemplateId) ?? store.templates[0] ?? null)
const currentCycleId = computed(() => activeTemplate.value?.cycle ?? store.activeCycleId)

onMounted(async () => {
  if (!store.activeCycleId) {
    await store.load()
  }
  await store.loadTemplates()
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

function togglePrimaryVisibleOnly(field: (typeof store.templateFields)[number], event: Event) {
  const target = event.target as HTMLInputElement
  store.updateTemplateField(field, {
    visible_rules: target.checked ? { visible_to: ['primary'] } : {},
  })
}

function togglePrimaryEditableOnly(field: (typeof store.templateFields)[number], event: Event) {
  const target = event.target as HTMLInputElement
  store.updateTemplateField(field, {
    editable_rules: target.checked ? { editable_by: ['primary'] } : {},
  })
}

function toggleFrozen(field: (typeof store.templateFields)[number], event: Event) {
  const target = event.target as HTMLInputElement
  store.updateTemplateField(field, { frozen: target.checked })
}

function toggleDashboardEnabled(field: (typeof store.templateFields)[number], event: Event) {
  const target = event.target as HTMLInputElement
  store.updateTemplateField(field, { dashboard_enabled: target.checked })
}

function toggleApprovalIncluded(field: (typeof store.templateFields)[number], event: Event) {
  const target = event.target as HTMLInputElement
  store.updateTemplateField(field, { approval_included: target.checked })
}

function updateWidth(field: (typeof store.templateFields)[number], event: Event) {
  const target = event.target as HTMLInputElement
  store.updateTemplateField(field, { width: Number(target.value || 160) })
}

function updateOptionSource(field: (typeof store.templateFields)[number], event: Event) {
  const target = event.target as HTMLInputElement
  store.updateTemplateField(field, { option_source: target.value.trim() })
}

function updateImportAliases(field: (typeof store.templateFields)[number], event: Event) {
  const target = event.target as HTMLInputElement
  store.updateTemplateField(field, {
    import_aliases: target.value
      .split(/[\n,]/)
      .map((item) => item.trim())
      .filter(Boolean),
  })
}

function updateFormulaInputType(event: Event) {
  const target = event.target as HTMLSelectElement
  store.templateFieldDraft.inputType = target.value as typeof store.templateFieldDraft.inputType
  if (
    ['select', 'multi_select', 'user', 'department', 'project'].includes(store.templateFieldDraft.inputType) &&
    store.templateFieldDraft.dataType !== 'option'
  ) {
    store.templateFieldDraft.dataType = 'option'
  }
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
      <p class="eyebrow">Schema Version {{ activeTemplate?.schema_version ?? '-' }}</p>
      <h1>模板管理</h1>
      <p class="page-note">
        {{ activeTemplate?.name ?? '未选择模板' }}
        <template v-if="activeTemplate?.copied_from_name"> · 复制自 {{ activeTemplate.copied_from_name }}</template>
      </p>
    </div>
    <div class="button-group dashboard-toolbar">
      <select v-model="store.activeTemplateId" class="dashboard-filter" :disabled="store.loading" @change="store.loadTemplateFields">
        <option v-for="template in store.templates" :key="template.id" :value="template.id">
          {{ template.name }} · {{ template.expense_type.toUpperCase() }} · v{{ template.schema_version }}
        </option>
      </select>
      <button class="secondary-button" type="button" :disabled="store.actionLoading || !currentCycleId" @click="store.bootstrapTemplatesFromPrevious(currentCycleId)">
        <Copy :size="16" />
        复制上一周期
      </button>
      <button class="secondary-button" type="button" :disabled="store.actionLoading || !store.activeTemplateId" @click="store.createTemplateRevision">
        <GitBranchPlus :size="16" />
        新建 Schema 修订
      </button>
      <button class="primary-button" type="button" :disabled="store.actionLoading" @click="store.createTemplateField">
        <Plus :size="17" />
        新增字段
      </button>
    </div>
  </section>

  <p v-if="store.error" class="error-banner">{{ store.error }}</p>

  <section class="content-grid">
    <article class="panel wide-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">{{ activeTemplate?.expense_type?.toUpperCase() ?? 'Template' }}</p>
          <h2>字段配置</h2>
        </div>
        <span class="status-chip">{{ activeTemplate?.status ?? 'Loading' }}</span>
      </div>
      <div class="field-list">
        <div class="field-form template-builder-form">
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
            <option value="number">数字输入</option>
            <option value="date">日期输入</option>
            <option value="select">单选下拉</option>
            <option value="multi_select">多选下拉</option>
            <option value="user">用户选择</option>
            <option value="department">部门选择</option>
            <option value="project">项目选择</option>
            <option value="formula">公式字段</option>
          </select>
          <input v-model="store.templateFieldDraft.optionSource" placeholder="option_source，如 masterdata.projects 或 A|B|C" />
          <input v-model="store.templateFieldDraft.importAliases" placeholder="导入别名，逗号分隔" />
          <input v-model.number="store.templateFieldDraft.width" type="number" min="80" step="10" placeholder="列宽" />
          <input
            v-if="store.templateFieldDraft.inputType === 'formula'"
            v-model="store.templateFieldDraft.formula"
            placeholder="公式，如 unit_price * total_quantity"
          />
          <label>
            <input v-model="store.templateFieldDraft.required" type="checkbox" />
            必填
          </label>
          <label>
            <input v-model="store.templateFieldDraft.frozen" type="checkbox" />
            冻结列
          </label>
          <label>
            <input v-model="store.templateFieldDraft.dashboardEnabled" type="checkbox" />
            Dashboard 字段
          </label>
          <label>
            <input v-model="store.templateFieldDraft.approvalIncluded" type="checkbox" />
            审批快照
          </label>
          <label>
            <input v-model="store.templateFieldDraft.primaryVisibleOnly" type="checkbox" />
            仅一级可见
          </label>
          <label>
            <input v-model="store.templateFieldDraft.primaryEditableOnly" type="checkbox" />
            仅一级可编辑
          </label>
        </div>
        <div v-for="field in store.templateFields" :key="field.id" class="template-field-card">
          <div class="template-field-main">
            <ListChecks :size="16" />
            <input class="field-label-input" :value="field.label" :disabled="store.actionLoading" @change="renameField(field, $event)" />
            <em>
              {{ field.code }} · {{ field.data_type }} · {{ field.input_type }}
              <template v-if="field.formula"> · 公式: {{ field.formula }}</template>
            </em>
          </div>
          <div class="template-field-grid">
            <label class="field-required-toggle">
              <input :checked="field.required" type="checkbox" :disabled="store.actionLoading" @change="toggleRequired(field, $event)" />
              必填
            </label>
            <label class="field-required-toggle">
              <input :checked="field.frozen" type="checkbox" :disabled="store.actionLoading" @change="toggleFrozen(field, $event)" />
              冻结列
            </label>
            <label class="field-required-toggle">
              <input :checked="field.dashboard_enabled ?? false" type="checkbox" :disabled="store.actionLoading" @change="toggleDashboardEnabled(field, $event)" />
              Dashboard 字段
            </label>
            <label class="field-required-toggle">
              <input :checked="field.approval_included ?? true" type="checkbox" :disabled="store.actionLoading" @change="toggleApprovalIncluded(field, $event)" />
              审批快照
            </label>
            <label class="field-required-toggle">
              <input
                :checked="field.visible_rules?.visible_to?.includes('primary') ?? false"
                type="checkbox"
                :disabled="store.actionLoading"
                @change="togglePrimaryVisibleOnly(field, $event)"
              />
              仅一级可见
            </label>
            <label class="field-required-toggle">
              <input
                :checked="field.editable_rules?.editable_by?.includes('primary') ?? false"
                type="checkbox"
                :disabled="store.actionLoading || field.input_type === 'formula'"
                @change="togglePrimaryEditableOnly(field, $event)"
              />
              仅一级可编辑
            </label>
            <input class="masterdata-input short" :value="field.width" type="number" min="80" step="10" :disabled="store.actionLoading" @change="updateWidth(field, $event)" />
            <input
              class="masterdata-input"
              :value="field.option_source"
              :disabled="store.actionLoading || !['select', 'multi_select'].includes(field.input_type)"
              placeholder="option_source"
              @change="updateOptionSource(field, $event)"
            />
            <input
              class="masterdata-input"
              :value="(field.import_aliases ?? []).join(', ')"
              :disabled="store.actionLoading"
              placeholder="导入别名"
              @change="updateImportAliases(field, $event)"
            />
            <button class="icon-button danger-icon" type="button" :disabled="store.actionLoading" @click="deleteField(field)">
              <Trash2 :size="15" />
            </button>
          </div>
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Rules</p>
          <h2>模板约束</h2>
        </div>
        <FunctionSquare :size="18" />
      </div>
      <div class="rule-stack">
        <p>总数量 = 1-12 月数量加总</p>
        <p>总金额 = 1-12 月金额加总</p>
        <p><Eye :size="15" />保密列仅一级预算管理员可见</p>
        <p><Settings2 :size="15" />下拉字段需配置 option_source，选择类字段统一按 option 口径存储</p>
        <p><Copy :size="15" />Schema Version {{ activeTemplate?.schema_version ?? '-' }}</p>
      </div>
    </article>
  </section>
</template>

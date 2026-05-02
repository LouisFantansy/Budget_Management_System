<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { CheckCheck, ClipboardList, FileInput, GitBranchPlus, Layers3, Plus, RefreshCw, Save, SendToBack } from 'lucide-vue-next'
import { apiGet, apiPatch, apiPost, type PaginatedResponse } from '../api/client'
import type {
  ApiDemandGenerateResponse,
  ApiDemandSchemaField,
  ApiDemandSheet,
  ApiDemandTemplate,
  ApiDepartment,
  ApiProject,
  ApiUser,
} from '../types/budget'

type DemandRowDraft = Record<string, unknown> & { _row_id: string }

const loading = ref(false)
const actionLoading = ref(false)
const error = ref('')
const success = ref('')

const demandTemplates = ref<ApiDemandTemplate[]>([])
const demandSheets = ref<ApiDemandSheet[]>([])
const departments = ref<ApiDepartment[]>([])
const users = ref<ApiUser[]>([])
const projects = ref<ApiProject[]>([])

const selectedSheetId = ref('')
const rawJsonVisible = ref(false)

const sheetCreateDraft = reactive({
  templateId: '',
  targetDepartmentId: '',
  dueAt: '',
})

const sheetEditor = reactive({
  rows: [] as DemandRowDraft[],
})

const selectedTemplate = computed(() => demandTemplates.value.find((item) => item.id === sheetCreateDraft.templateId) ?? null)
const selectedSheet = computed(() => demandSheets.value.find((item) => item.id === selectedSheetId.value) ?? null)
const editorSchema = computed(() => selectedSheet.value?.schema_snapshot ?? [])
const editableRows = computed(() => sheetEditor.rows)
const selectableDepartments = computed(() => {
  if (selectedTemplate.value?.target_mode === 'ss_public') {
    return departments.value.filter((item) => item.level === 'ss_public')
  }
  return departments.value.filter((item) => item.level === 'secondary')
})
const visibleTemplateFields = computed(() => editorSchema.value.filter((field) => field.user_permissions?.visible !== false))
const editableTemplateFields = computed(() => visibleTemplateFields.value.filter((field) => field.code !== 'budget_no'))
const canCreateSheet = computed(() => !!sheetCreateDraft.templateId && !!sheetCreateDraft.targetDepartmentId)
const canEditSelectedSheet = computed(() => selectedSheet.value?.workflow_actions?.can_edit_payload ?? false)
const currentUserId = ref<number | null>(null)

function hydrateRows(payload: Array<Record<string, unknown>>) {
  sheetEditor.rows = payload.map((row, index) => ({
    _row_id: String(row._row_id ?? `row-${index + 1}`),
    ...row,
  }))
}

function departmentName(id: string | null) {
  if (!id) return '-'
  return departments.value.find((item) => item.id === id)?.name ?? id
}

function userName(id: number | null | undefined, fallback = '-') {
  if (!id) return fallback
  return users.value.find((item) => item.id === id)?.display_name || users.value.find((item) => item.id === id)?.username || fallback
}

function formatDateTime(value: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function optionValues(field: ApiDemandSchemaField) {
  const source = field.option_source?.trim() ?? ''
  if (!source) return []
  if (source === 'masterdata.projects') return projects.value.map((item) => item.name)
  if (source === 'masterdata.departments') return departments.value.map((item) => item.name)
  if (source === 'system.users') return users.value.map((item) => item.display_name || item.username)
  return source
    .split('|')
    .map((item) => item.trim())
    .filter(Boolean)
}

function fieldPlaceholder(field: ApiDemandSchemaField) {
  if (field.input_type === 'project') return '选择项目'
  if (field.input_type === 'department') return '选择部门'
  if (field.input_type === 'user') return '选择人员'
  if (field.input_type === 'date') return '选择日期'
  return `填写${field.label}`
}

function isSelectLikeField(field: ApiDemandSchemaField) {
  return ['select', 'project', 'department', 'user'].includes(field.input_type)
}

function baseValueForField(field: ApiDemandSchemaField) {
  if (field.input_type === 'multi_select') return []
  if (field.data_type === 'boolean') return false
  if (field.data_type === 'number' || field.data_type === 'money') return ''
  return ''
}

function newRow() {
  const row: DemandRowDraft = {
    _row_id: `row-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  }
  visibleTemplateFields.value.forEach((field) => {
    row[field.code] = baseValueForField(field)
  })
  return row
}

function addRow() {
  sheetEditor.rows = [...sheetEditor.rows, newRow()]
}

function removeRow(rowId: string) {
  sheetEditor.rows = sheetEditor.rows.filter((item) => item._row_id !== rowId)
}

function syncCreateDepartment() {
  const options = selectableDepartments.value
  if (!options.length) {
    sheetCreateDraft.targetDepartmentId = ''
    return
  }
  if (!options.some((item) => item.id === sheetCreateDraft.targetDepartmentId)) {
    sheetCreateDraft.targetDepartmentId = options[0].id
  }
}

function onTemplateChange() {
  syncCreateDepartment()
}

function setSelectedSheet(sheetId: string) {
  selectedSheetId.value = sheetId
  const sheet = demandSheets.value.find((item) => item.id === sheetId)
  hydrateRows(sheet?.payload ?? [])
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [templatesPage, sheetsPage, departmentsPage, usersPage, projectsPage, currentUser] = await Promise.all([
      apiGet<PaginatedResponse<ApiDemandTemplate>>('/demand-templates/'),
      apiGet<PaginatedResponse<ApiDemandSheet>>('/demand-sheets/'),
      apiGet<PaginatedResponse<ApiDepartment>>('/departments/'),
      apiGet<PaginatedResponse<ApiUser>>('/users/'),
      apiGet<PaginatedResponse<ApiProject>>('/projects/'),
      apiGet<ApiUser>('/auth/me/'),
    ])
    demandTemplates.value = templatesPage.results
    demandSheets.value = sheetsPage.results
    departments.value = departmentsPage.results
    users.value = usersPage.results
    projects.value = projectsPage.results
    currentUserId.value = currentUser.id
    if (!sheetCreateDraft.templateId && templatesPage.results.length) {
      sheetCreateDraft.templateId = templatesPage.results[0].id
    }
    syncCreateDepartment()
    if (selectedSheetId.value) {
      const matched = sheetsPage.results.find((item) => item.id === selectedSheetId.value)
      if (matched) {
        hydrateRows(matched.payload)
      } else {
        selectedSheetId.value = ''
        sheetEditor.rows = []
      }
    } else if (sheetsPage.results.length) {
      setSelectedSheet(sheetsPage.results[0].id)
    }
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : '加载专题需求数据失败。'
  } finally {
    loading.value = false
  }
}

async function createSheet() {
  if (!canCreateSheet.value) {
    error.value = '请先选择模板和目标部门。'
    return
  }
  actionLoading.value = true
  error.value = ''
  success.value = ''
  try {
    const created = await apiPost<ApiDemandSheet>('/demand-sheets/', {
      template: sheetCreateDraft.templateId,
      target_department: sheetCreateDraft.targetDepartmentId,
      due_at: sheetCreateDraft.dueAt || null,
    })
    success.value = '专题需求任务已创建。'
    await load()
    setSelectedSheet(created.id)
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : '创建专题需求任务失败。'
  } finally {
    actionLoading.value = false
  }
}

async function saveSheet() {
  if (!selectedSheet.value) return
  actionLoading.value = true
  error.value = ''
  success.value = ''
  try {
    const saved = await apiPatch<ApiDemandSheet>(`/demand-sheets/${selectedSheet.value.id}/`, {
      payload: sheetEditor.rows,
    })
    success.value = '专题需求内容已保存。'
    await load()
    setSelectedSheet(saved.id)
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : '保存专题需求失败。'
  } finally {
    actionLoading.value = false
  }
}

async function runSheetAction(action: 'submit' | 'confirm' | 'reopen') {
  if (!selectedSheet.value) return
  actionLoading.value = true
  error.value = ''
  success.value = ''
  try {
    const updated = await apiPost<ApiDemandSheet>(`/demand-sheets/${selectedSheet.value.id}/${action}/`, {})
    const messages = {
      submit: '专题需求已提交。',
      confirm: '专题需求已确认。',
      reopen: '专题需求已重新打开。',
    }
    success.value = messages[action]
    await load()
    setSelectedSheet(updated.id)
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : '专题需求流转失败。'
  } finally {
    actionLoading.value = false
  }
}

async function generateSheet() {
  if (!selectedSheet.value) return
  actionLoading.value = true
  error.value = ''
  success.value = ''
  try {
    const result = await apiPost<ApiDemandGenerateResponse>(`/demand-sheets/${selectedSheet.value.id}/generate-budget-lines/`, {
      force_rebuild: true,
    })
    success.value = `已同步 ${result.generated_line_count} 条专题预算，Draft 版本 ${result.version.id}。`
    await load()
    setSelectedSheet(result.sheet_id)
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : '生成专题预算失败。'
  } finally {
    actionLoading.value = false
  }
}

function updateField(row: DemandRowDraft, field: ApiDemandSchemaField, event: Event) {
  const target = event.target as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
  if (field.data_type === 'boolean') {
    row[field.code] = (target as HTMLInputElement).checked
    return
  }
  if (field.input_type === 'multi_select') {
    row[field.code] = target.value
      .split(/[\n,|]/)
      .map((item) => item.trim())
      .filter(Boolean)
    return
  }
  row[field.code] = target.value
}

function fieldDisplayValue(row: DemandRowDraft, field: ApiDemandSchemaField) {
  const value = row[field.code]
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'boolean') return value ? '是' : '否'
  return value === undefined || value === null ? '' : String(value)
}

function isFieldEditable(field: ApiDemandSchemaField) {
  return canEditSelectedSheet.value && field.user_permissions?.editable !== false
}

onMounted(() => {
  load()
})
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">Demand Workflow</p>
      <h1>专题需求</h1>
    </div>
    <div class="button-group">
      <button class="secondary-button" type="button" :disabled="loading || actionLoading" @click="load">
        <RefreshCw :size="17" />
        刷新
      </button>
      <button class="primary-button" type="button" :disabled="actionLoading || !canCreateSheet" @click="createSheet">
        <FileInput :size="17" />
        创建任务
      </button>
    </div>
  </section>

  <p v-if="error" class="error-banner">{{ error }}</p>
  <p v-else-if="success" class="success-banner">{{ success }}</p>

  <section class="content-grid demand-page-grid">
    <article class="panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Templates</p>
          <h2>模板分发</h2>
        </div>
        <Layers3 :size="18" />
      </div>

      <div class="field-form demand-form-grid">
        <select v-model="sheetCreateDraft.templateId" :disabled="actionLoading" @change="onTemplateChange">
          <option value="">选择专题模板</option>
          <option v-for="template in demandTemplates" :key="template.id" :value="template.id">
            {{ template.name }} · {{ template.target_mode === 'ss_public' ? 'SS public' : '二级部门' }}
          </option>
        </select>
        <select v-model="sheetCreateDraft.targetDepartmentId" :disabled="actionLoading">
          <option value="">选择目标部门</option>
          <option v-for="department in selectableDepartments" :key="department.id" :value="department.id">
            {{ department.name }}
          </option>
        </select>
        <input v-model="sheetCreateDraft.dueAt" type="datetime-local" :disabled="actionLoading" />
      </div>

      <div v-if="selectedTemplate" class="detail-grid">
        <div class="detail-card">
          <span>模板名称</span>
          <strong>{{ selectedTemplate.name }}</strong>
        </div>
        <div class="detail-card">
          <span>预算类型</span>
          <strong>{{ selectedTemplate.expense_type.toUpperCase() }}</strong>
        </div>
        <div class="detail-card">
          <span>挂载方式</span>
          <strong>{{ selectedTemplate.target_mode === 'ss_public' ? 'SS public' : '按二级部门' }}</strong>
        </div>
        <div class="detail-card">
          <span>可填写字段</span>
          <strong>{{ selectedTemplate.schema.length }}</strong>
        </div>
      </div>

      <div v-if="selectedTemplate" class="demand-template-fields">
        <div v-for="field in selectedTemplate.schema" :key="`${selectedTemplate.id}-${field.code}`" class="demand-template-field">
          <strong>{{ field.label }}</strong>
          <span>{{ field.code }} · {{ field.input_type }}{{ field.required ? ' · 必填' : '' }}</span>
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Tasks</p>
          <h2>填写任务</h2>
        </div>
        <ClipboardList :size="18" />
      </div>

      <div v-if="demandSheets.length" class="task-list">
        <button
          v-for="sheet in demandSheets"
          :key="sheet.id"
          type="button"
          class="task-row task-row-stack demand-task-row"
          :class="{ 'task-row-active': sheet.id === selectedSheetId }"
          @click="setSelectedSheet(sheet.id)"
        >
          <div>
            <strong>{{ sheet.template_name }}</strong>
            <span>{{ sheet.target_department_name || departmentName(sheet.target_department) }}</span>
          </div>
          <div class="demand-task-meta">
            <span class="status-chip">{{ sheet.status_label || sheet.status }}</span>
            <span>{{ sheet.sync_status_label }}</span>
            <span>{{ sheet.generated_line_count }} 条</span>
          </div>
        </button>
      </div>
      <p v-else class="empty-note">当前还没有专题需求任务。</p>
    </article>
  </section>

  <section v-if="selectedSheet" class="panel">
    <div class="panel-title">
      <div>
        <p class="eyebrow">{{ selectedSheet.template_name }}</p>
        <h2>结构化填报</h2>
      </div>
      <div class="button-group">
        <span class="status-chip">{{ selectedSheet.status_label || selectedSheet.status }}</span>
        <span class="status-chip">{{ selectedSheet.sync_status_label }}</span>
      </div>
    </div>

    <div class="detail-grid">
      <div class="detail-card">
        <span>填报部门</span>
        <strong>{{ selectedSheet.target_department_name || departmentName(selectedSheet.target_department) }}</strong>
      </div>
      <div class="detail-card">
        <span>要求完成</span>
        <strong>{{ formatDateTime(selectedSheet.due_at) }}</strong>
      </div>
      <div class="detail-card">
        <span>提交人</span>
        <strong>{{ userName(selectedSheet.submitted_by, '-') }}</strong>
      </div>
      <div class="detail-card">
        <span>确认人</span>
        <strong>{{ userName(selectedSheet.confirmed_by, '-') }}</strong>
      </div>
      <div class="detail-card">
        <span>最近同步</span>
        <strong>{{ formatDateTime(selectedSheet.generated_at) }}</strong>
      </div>
      <div class="detail-card">
        <span>同步条数</span>
        <strong>{{ selectedSheet.generated_line_count }}</strong>
      </div>
    </div>

    <div class="button-group demand-actions">
      <button class="secondary-button" type="button" :disabled="actionLoading || !selectedSheet.workflow_actions.can_edit_payload" @click="addRow">
        <Plus :size="16" />
        新增行
      </button>
      <button class="secondary-button" type="button" :disabled="actionLoading || !selectedSheet.workflow_actions.can_edit_payload" @click="saveSheet">
        <Save :size="16" />
        保存
      </button>
      <button class="secondary-button" type="button" :disabled="actionLoading || !selectedSheet.workflow_actions.can_submit" @click="runSheetAction('submit')">
        <SendToBack :size="16" />
        提交填写
      </button>
      <button class="secondary-button" type="button" :disabled="actionLoading || !selectedSheet.workflow_actions.can_confirm" @click="runSheetAction('confirm')">
        <CheckCheck :size="16" />
        一级确认
      </button>
      <button class="secondary-button" type="button" :disabled="actionLoading || !selectedSheet.workflow_actions.can_reopen" @click="runSheetAction('reopen')">
        <GitBranchPlus :size="16" />
        重新打开
      </button>
      <button class="primary-button" type="button" :disabled="actionLoading || !selectedSheet.workflow_actions.can_generate" @click="generateSheet">
        <FileInput :size="16" />
        同步预算
      </button>
    </div>

    <div class="demand-editor-list">
      <article v-for="(row, rowIndex) in editableRows" :key="row._row_id" class="demand-row-card">
        <div class="panel-title demand-row-title">
          <div>
            <p class="eyebrow">Row {{ rowIndex + 1 }}</p>
            <h3>{{ String(row.description || '未命名需求') }}</h3>
          </div>
          <button
            v-if="selectedSheet.workflow_actions.can_edit_payload"
            class="text-button danger-text"
            type="button"
            :disabled="actionLoading"
            @click="removeRow(row._row_id)"
          >
            删除
          </button>
        </div>

        <div class="field-form demand-row-grid">
          <label v-for="field in editableTemplateFields" :key="`${row._row_id}-${field.code}`">
            {{ field.label }}<span v-if="field.required"> *</span>
            <input
              v-if="field.input_type === 'text' || field.input_type === 'number'"
              :value="fieldDisplayValue(row, field)"
              :type="field.data_type === 'date' ? 'date' : field.data_type === 'money' || field.data_type === 'number' ? 'number' : 'text'"
              :step="field.data_type === 'money' ? '0.01' : field.data_type === 'number' ? '0.01' : undefined"
              :placeholder="fieldPlaceholder(field)"
              :disabled="actionLoading || !isFieldEditable(field)"
              @input="updateField(row, field, $event)"
            />
            <input
              v-else-if="field.input_type === 'date'"
              :value="fieldDisplayValue(row, field)"
              type="date"
              :disabled="actionLoading || !isFieldEditable(field)"
              @input="updateField(row, field, $event)"
            />
            <select
              v-else-if="isSelectLikeField(field)"
              :value="fieldDisplayValue(row, field)"
              :disabled="actionLoading || !isFieldEditable(field)"
              @change="updateField(row, field, $event)"
            >
              <option value="">请选择</option>
              <option v-for="option in optionValues(field)" :key="`${field.code}-${option}`" :value="option">
                {{ option }}
              </option>
            </select>
            <textarea
              v-else-if="field.input_type === 'multi_select'"
              :value="fieldDisplayValue(row, field)"
              :disabled="actionLoading || !isFieldEditable(field)"
              placeholder="多值请用逗号、竖线或换行分隔"
              @input="updateField(row, field, $event)"
            ></textarea>
            <label v-else-if="field.data_type === 'boolean'" class="checkbox-field">
              <input
                :checked="Boolean(row[field.code])"
                type="checkbox"
                :disabled="actionLoading || !isFieldEditable(field)"
                @change="updateField(row, field, $event)"
              />
              <span>{{ Boolean(row[field.code]) ? '是' : '否' }}</span>
            </label>
            <input
              v-else
              :value="fieldDisplayValue(row, field)"
              :disabled="actionLoading || !isFieldEditable(field)"
              :placeholder="fieldPlaceholder(field)"
              @input="updateField(row, field, $event)"
            />
          </label>
        </div>
      </article>
    </div>

    <button class="text-button" type="button" :disabled="actionLoading" @click="rawJsonVisible = !rawJsonVisible">
      {{ rawJsonVisible ? '收起 JSON 预览' : '展开 JSON 预览' }}
    </button>
    <textarea
      v-if="rawJsonVisible"
      :value="JSON.stringify(sheetEditor.rows, null, 2)"
      class="import-textarea demand-payload"
      readonly
      spellcheck="false"
    ></textarea>
  </section>

  <p v-else class="empty-note">选择左侧任务后，可进行结构化填写、确认和预算同步。</p>
</template>

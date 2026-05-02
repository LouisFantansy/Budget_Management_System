<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { FileInput, Layers3, RefreshCw, SendToBack } from 'lucide-vue-next'
import { apiGet, apiPost, type PaginatedResponse } from '../api/client'
import type {
  ApiDemandGenerateResponse,
  ApiDemandSheet,
  ApiDemandTemplate,
  ApiDepartment,
} from '../types/budget'

const loading = ref(false)
const actionLoading = ref(false)
const error = ref('')
const success = ref('')

const demandTemplates = ref<ApiDemandTemplate[]>([])
const demandSheets = ref<ApiDemandSheet[]>([])
const departments = ref<ApiDepartment[]>([])

const sheetDraft = reactive({
  templateId: '',
  targetDepartmentId: '',
  payloadText: JSON.stringify(
    [
      {
        budget_no: 'DEM-ARCH-001',
        description: '专题采购需求示例',
        total_amount: '10000.00',
        unit_price: '5000.00',
        total_quantity: '2',
        reason: '年度公共能力建设',
        monthly_plans: [{ month: 3, amount: '5000.00' }, { month: 9, amount: '5000.00' }],
      },
    ],
    null,
    2,
  ),
})

const selectedTemplate = computed(() => demandTemplates.value.find((item) => item.id === sheetDraft.templateId) ?? null)
const selectableDepartments = computed(() => {
  if (selectedTemplate.value?.target_mode === 'ss_public') {
    return departments.value.filter((item) => item.level === 'ss_public')
  }
  return departments.value.filter((item) => item.level === 'secondary')
})

function departmentName(id: string | null) {
  if (!id) return '-'
  return departments.value.find((item) => item.id === id)?.name ?? id
}

function parsePayload() {
  try {
    const payload = JSON.parse(sheetDraft.payloadText)
    if (!Array.isArray(payload)) {
      throw new Error('payload must be an array')
    }
    return payload
  } catch {
    throw new Error('专题需求内容必须是合法 JSON 数组。')
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [templatesPage, sheetsPage, departmentsPage] = await Promise.all([
      apiGet<PaginatedResponse<ApiDemandTemplate>>('/demand-templates/'),
      apiGet<PaginatedResponse<ApiDemandSheet>>('/demand-sheets/'),
      apiGet<PaginatedResponse<ApiDepartment>>('/departments/'),
    ])
    demandTemplates.value = templatesPage.results
    demandSheets.value = sheetsPage.results
    departments.value = departmentsPage.results
    if (!sheetDraft.templateId && templatesPage.results.length) {
      sheetDraft.templateId = templatesPage.results[0].id
    }
    syncDraftDepartment()
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : '加载专题需求数据失败。'
  } finally {
    loading.value = false
  }
}

function syncDraftDepartment() {
  const options = selectableDepartments.value
  if (!options.length) {
    sheetDraft.targetDepartmentId = ''
    return
  }
  if (!options.some((item) => item.id === sheetDraft.targetDepartmentId)) {
    sheetDraft.targetDepartmentId = options[0].id
  }
}

function onTemplateChange() {
  syncDraftDepartment()
}

async function createSheet() {
  if (!sheetDraft.templateId || !sheetDraft.targetDepartmentId) {
    error.value = '请先选择模板和目标部门。'
    return
  }
  actionLoading.value = true
  error.value = ''
  success.value = ''
  try {
    const payload = parsePayload()
    await apiPost<ApiDemandSheet>('/demand-sheets/', {
      template: sheetDraft.templateId,
      target_department: sheetDraft.targetDepartmentId,
      payload,
    })
    success.value = '专题需求表已创建。'
    await load()
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : '创建专题需求表失败。'
  } finally {
    actionLoading.value = false
  }
}

async function generateSheet(sheet: ApiDemandSheet) {
  actionLoading.value = true
  error.value = ''
  success.value = ''
  try {
    const result = await apiPost<ApiDemandGenerateResponse>(`/demand-sheets/${sheet.id}/generate-budget-lines/`, {
      confirm: true,
      force_rebuild: true,
    })
    success.value = `已生成 ${result.generated_line_count} 条专题预算，Draft 版本 ${result.version.id}。`
    await load()
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : '生成专题预算失败。'
  } finally {
    actionLoading.value = false
  }
}

onMounted(() => {
  load()
})
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">Demand Forms</p>
      <h1>专题需求</h1>
    </div>
    <div class="button-group">
      <button class="secondary-button" type="button" :disabled="loading || actionLoading" @click="load">
        <RefreshCw :size="17" />
        刷新
      </button>
      <button class="primary-button" type="button" :disabled="actionLoading" @click="createSheet">
        <FileInput :size="17" />
        创建需求表
      </button>
    </div>
  </section>

  <p v-if="error" class="error-banner">{{ error }}</p>
  <p v-else-if="success" class="success-banner">{{ success }}</p>

  <section class="content-grid">
    <article class="panel wide-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Templates</p>
          <h2>模板与创建</h2>
        </div>
        <Layers3 :size="18" />
      </div>

      <div class="field-form demand-form-grid">
        <select v-model="sheetDraft.templateId" :disabled="actionLoading" @change="onTemplateChange">
          <option value="">选择专题模板</option>
          <option v-for="template in demandTemplates" :key="template.id" :value="template.id">
            {{ template.name }} · {{ template.target_mode === 'ss_public' ? 'SS public' : '二级部门' }}
          </option>
        </select>
        <select v-model="sheetDraft.targetDepartmentId" :disabled="actionLoading">
          <option value="">选择目标部门</option>
          <option v-for="department in selectableDepartments" :key="department.id" :value="department.id">
            {{ department.name }}
          </option>
        </select>
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
          <strong>{{ selectedTemplate.target_mode === 'ss_public' ? 'SS public 一级编制' : '挂到二级部门' }}</strong>
        </div>
        <div class="detail-card">
          <span>归属部门</span>
          <strong>{{ departmentName(selectedTemplate.target_department) }}</strong>
        </div>
      </div>

      <textarea
        v-model="sheetDraft.payloadText"
        class="import-textarea demand-payload"
        spellcheck="false"
        placeholder="输入专题需求 JSON 数组。每行至少包含 description 和 total_amount。"
      ></textarea>
      <p class="empty-note">
        `SS public` 模板仅允许一级预算管理员直接挂到 `SS public`，不会分摊到二级部门。
      </p>
    </article>

    <article class="panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Recent Sheets</p>
          <h2>生成记录</h2>
        </div>
        <SendToBack :size="18" />
      </div>

      <div v-if="demandSheets.length" class="task-list">
        <div v-for="sheet in demandSheets" :key="sheet.id" class="task-row task-row-dense">
          <div>
            <strong>{{ sheet.template_name }}</strong>
            <span>{{ departmentName(sheet.target_department) }} · {{ sheet.generated_line_count }} 条 · {{ sheet.status }}</span>
          </div>
          <div class="task-tail">
            <span class="status-chip">{{ sheet.generated_budget_book_status || '未生成' }}</span>
            <button class="text-button" type="button" :disabled="actionLoading" @click="generateSheet(sheet)">
              生成预算
            </button>
          </div>
        </div>
      </div>
      <p v-else class="empty-note">当前还没有专题需求表。</p>
    </article>
  </section>
</template>

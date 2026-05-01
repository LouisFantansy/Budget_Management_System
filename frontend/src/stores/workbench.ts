import { defineStore } from 'pinia'
import { apiDelete, apiGet, apiPatch, apiPost, type PaginatedResponse } from '../api/client'
import type {
  ApiApprovalRequest,
  ApiBudgetBook,
  ApiBudgetLine,
  ApiBudgetOverview,
  ApiBudgetTemplate,
  ApiBudgetVersion,
  ApiCategory,
  ApiTemplateField,
  ApiUser,
  ApiNamedMasterData,
  ApiProject,
  ApiVersionDiff,
  ApprovalItem,
  BudgetLinePreview,
  BudgetTask,
  MasterDataKind,
  SummaryStat,
  VersionContext,
} from '../types/budget'

const departmentNames: Record<string, string> = {}
const categoryNames: Record<string, string> = {}
const projectNames: Record<string, string> = {}

function money(value: string | number) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return '¥ 0'
  if (numberValue >= 1_000_000) return `¥ ${(numberValue / 1_000_000).toFixed(1)}M`
  if (numberValue >= 1_000) return `¥ ${(numberValue / 1_000).toFixed(1)}K`
  return `¥ ${numberValue.toFixed(0)}`
}

function sourceLabel(source: string) {
  const labels: Record<string, string> = {
    self_built: '二级自编',
    special: '专题生成',
    ss_public: 'SS public',
    group_allocation: '集团分摊',
    primary_consolidated: '一级总表',
  }
  return labels[source] ?? source
}

function defaultValueForField(field: ApiTemplateField) {
  if (field.data_type === 'number' || field.data_type === 'money') return '0'
  if (field.data_type === 'date') return new Date().toISOString().slice(0, 10)
  if (field.data_type === 'boolean') return false
  if (field.data_type === 'json') return {}
  return '待补充'
}

export const useWorkbenchStore = defineStore('workbench', {
  state: () => ({
    loading: false,
    actionLoading: false,
    error: '',
    currentUser: null as ApiUser | null,
    loginForm: {
      username: 'primary-admin',
      password: 'password',
    },
    activeDraftVersionId: '',
    activeDraftDepartmentId: '',
    activeTemplateId: '',
    revisionSourceBookId: '',
    versionDiff: null as ApiVersionDiff | null,
    budgetOverview: null as ApiBudgetOverview | null,
    templateFields: [] as ApiTemplateField[],
    templates: [] as ApiBudgetTemplate[],
    templateFieldDraft: {
      code: '',
      label: '',
      dataType: 'text' as ApiTemplateField['data_type'],
      required: false,
    },
    masterDataKind: 'categories' as MasterDataKind,
    masterDataDraft: {
      code: '',
      name: '',
    },
    masterData: {
      categories: [] as ApiCategory[],
      projects: [] as ApiProject[],
      vendors: [] as ApiNamedMasterData[],
      regions: [] as ApiNamedMasterData[],
    },
    fieldErrors: {} as Record<string, string>,
    cycleName: '2027 年度预算编制',
    versionContext: 'latest_approved' as VersionContext,
    summaryStats: [
      { label: 'OPEX Approved', value: '¥ 48.6M', delta: '+6.8% YoY', tone: 'blue' },
      { label: 'CAPEX Approved', value: '¥ 21.4M', delta: '+3.1% YoY', tone: 'green' },
      { label: '送审中版本', value: '7', delta: '3 个今日到期', tone: 'amber' },
      { label: '待同步部门', value: '2', delta: '有新 Approved', tone: 'red' },
    ] as SummaryStat[],
    tasks: [
      { department: '平台软件部', owner: '主预算管理员', status: '二级审批中', version: 'Draft #4', amount: '¥ 12.8M' },
      { department: '硬件系统部', owner: '主预算管理员', status: '已 Approved', version: 'V3', amount: '¥ 18.2M' },
      { department: 'SS public', owner: '一级预算管理员', status: '编制中', version: 'Draft #2', amount: '¥ 6.7M' },
    ] as BudgetTask[],
    approvals: [
      { title: '平台软件部 OPEX 修订送审', department: '平台软件部', versionContext: 'submitted_version', amount: '¥ 9.6M', due: '今天' },
      { title: '一级总表初版审核', department: '一级研发组织', versionContext: 'current_draft', amount: '¥ 70.0M', due: '明天' },
    ] as ApprovalItem[],
    budgetLines: [
      { budgetNo: 'OPEX-0018', description: '研发云测试资源扩容', category: 'Cloud Service', project: 'TD 项目', owner: '平台软件部', amount: '¥ 1.42M', source: '二级自编', locked: false },
      { budgetNo: 'OPEX-0021', description: '年度 IDE License 集采', category: 'Software', project: '公共能力', owner: 'SS public', amount: '¥ 0.86M', source: '专题生成', locked: true },
      { budgetNo: 'CAPEX-0007', description: '自动化测试服务器', category: 'Server', project: '产品项目', owner: '硬件系统部', amount: '¥ 2.30M', source: '专题生成', locked: true },
    ] as BudgetLinePreview[],
  }),
  actions: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        const [departments, categories, projects, books, approvals] = await Promise.all([
          apiGet<PaginatedResponse<{ id: string; name: string }>>('/departments/'),
          apiGet<PaginatedResponse<{ id: string; name: string }>>('/categories/'),
          apiGet<PaginatedResponse<{ id: string; name: string }>>('/projects/'),
          apiGet<PaginatedResponse<ApiBudgetBook>>('/budget-books/'),
          apiGet<PaginatedResponse<ApiApprovalRequest>>('/approval-requests/'),
        ])

        departments.results.forEach((item) => {
          departmentNames[item.id] = item.name
        })
        categories.results.forEach((item) => {
          categoryNames[item.id] = item.name
        })
        projects.results.forEach((item) => {
          projectNames[item.id] = item.name
        })

        this.tasks = books.results.map((book) => ({
          bookId: book.id,
          currentDraftId: book.current_draft,
          department: departmentNames[book.department] ?? book.department,
          owner: book.status === 'approved' ? '已审批版本' : '预算管理员',
          status: book.status,
          version: book.latest_approved_version ? 'Approved' : book.current_draft ? 'Draft' : '未开始',
          amount: book.latest_approved_version ? '已生成' : '编制中',
        }))

        this.approvals = approvals.results.map((item) => ({
          id: item.id,
          title: item.title,
          department: departmentNames[item.department] ?? item.department,
          versionContext: item.dashboard_context.version_context ?? 'submitted_version',
          amount: '待审批',
          due: item.status === 'pending' ? '待处理' : item.status,
        }))

        const versionIds = books.results
          .map((book) => book.latest_approved_version ?? book.current_draft)
          .filter((id): id is string => Boolean(id))
        const linePages = await Promise.all(
          versionIds.map((versionId) => apiGet<PaginatedResponse<ApiBudgetLine>>(`/budget-lines/?version=${versionId}`)),
        )
        this.budgetLines = linePages.flatMap((page) =>
          page.results.map((line) => ({
            id: line.id,
            versionId: line.version,
            departmentId: line.department,
            dynamicData: line.dynamic_data,
            budgetNo: line.budget_no,
            description: line.description,
            category: line.category ? categoryNames[line.category] ?? line.category : '-',
            project: line.project ? projectNames[line.project] ?? line.project : '-',
            owner: departmentNames[line.department] ?? line.department,
            amount: money(line.total_amount),
            source: line.source_ref_type ? sourceLabel(line.source_ref_type) : '二级自编',
            locked: !line.editable_by_secondary,
          })),
        )
        const editableBook = books.results.find((book) => book.current_draft)
        this.activeDraftVersionId = editableBook?.current_draft ?? ''
        this.activeDraftDepartmentId = editableBook?.department ?? ''
        this.activeTemplateId = editableBook?.template ?? books.results[0]?.template ?? ''
        this.revisionSourceBookId = books.results.find((book) => !book.current_draft && book.latest_approved_version)?.id ?? ''
        await this.loadTemplateFields()

        const approvedLines = this.budgetLines.length
        const totalAmount = linePages
          .flatMap((page) => page.results)
          .reduce((sum, line) => sum + Number(line.total_amount), 0)
        this.summaryStats = [
          { label: '预算条目', value: String(approvedLines), delta: '来自真实 API', tone: 'blue' },
          { label: '预算金额', value: money(totalAmount), delta: 'Draft + Approved', tone: 'green' },
          { label: '送审中版本', value: String(approvals.count), delta: '审批请求', tone: 'amber' },
          { label: '预算表', value: String(books.count), delta: 'OPEX/CAPEX Book', tone: 'red' },
        ]
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载失败'
      } finally {
        this.loading = false
      }
    },
    async loadMe() {
      try {
        this.currentUser = await apiGet<ApiUser>('/auth/me/')
      } catch {
        this.currentUser = null
      }
    },
    async login() {
      this.actionLoading = true
      this.error = ''
      try {
        this.currentUser = await apiPost<ApiUser>('/auth/login/', this.loginForm)
        await this.load()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '登录失败'
      } finally {
        this.actionLoading = false
      }
    },
    async logout() {
      this.actionLoading = true
      this.error = ''
      try {
        await apiPost('/auth/logout/')
        this.currentUser = null
      } catch (error) {
        this.error = error instanceof Error ? error.message : '退出失败'
      } finally {
        this.actionLoading = false
      }
    },
    async approveApproval(id: string) {
      await this.runApprovalAction(id, 'approve')
    },
    async rejectApproval(id: string) {
      await this.runApprovalAction(id, 'reject')
    },
    async runApprovalAction(id: string, action: 'approve' | 'reject') {
      this.actionLoading = true
      this.error = ''
      try {
        await apiPost(`/approval-requests/${id}/${action}/`)
        await this.load()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '审批操作失败'
      } finally {
        this.actionLoading = false
      }
    },
    async createDraftLine() {
      if (!this.activeDraftVersionId || !this.activeDraftDepartmentId) {
        this.error = '当前没有可编辑 Draft 版本'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        await apiPost('/budget-lines/', {
          version: this.activeDraftVersionId,
          department: this.activeDraftDepartmentId,
          line_no: this.budgetLines.length + 1,
          budget_no: `DRAFT-${Date.now()}`,
          description: '新增预算条目',
          unit_price: '0.00',
          total_quantity: '0.00',
          total_amount: '0.00',
          dynamic_data: this.defaultDynamicData(),
        })
        await this.load()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '新增预算条目失败'
      } finally {
        this.actionLoading = false
      }
    },
    async submitActiveDraft() {
      if (!this.activeDraftVersionId) {
        this.error = '当前没有可提交的 Draft 版本'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        await apiPost(`/budget-versions/${this.activeDraftVersionId}/submit/`)
        await this.load()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '提交送审失败'
      } finally {
        this.actionLoading = false
      }
    },
    async createRevisionDraft() {
      if (!this.revisionSourceBookId) {
        this.error = '当前没有可修订的 Approved 预算表'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        await apiPost(`/budget-books/${this.revisionSourceBookId}/create-revision/`)
        await this.load()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '创建修订 Draft 失败'
      } finally {
        this.actionLoading = false
      }
    },
    async loadVersionDiff() {
      this.loading = true
      this.error = ''
      try {
        const versions = await apiGet<PaginatedResponse<ApiBudgetVersion>>('/budget-versions/')
        const target = versions.results.find((version) => version.base_version)
        if (!target) {
          this.versionDiff = null
          return
        }
        this.versionDiff = await apiGet<ApiVersionDiff>(`/budget-versions/${target.id}/diff/`)
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载版本差异失败'
      } finally {
        this.loading = false
      }
    },
    async loadBudgetOverview(context: VersionContext = 'latest_approved') {
      this.loading = true
      this.error = ''
      try {
        this.budgetOverview = await apiGet<ApiBudgetOverview>(`/dashboard-configs/budget-overview/?version_context=${context}`)
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载预算看板失败'
      } finally {
        this.loading = false
      }
    },
    async loadTemplateFields() {
      if (!this.activeTemplateId) {
        this.templateFields = []
        return
      }
      const fields = await apiGet<PaginatedResponse<ApiTemplateField>>(`/template-fields/?template=${this.activeTemplateId}`)
      this.templateFields = fields.results.sort((left, right) => left.order - right.order)
    },
    async loadTemplates() {
      this.loading = true
      this.error = ''
      try {
        const templates = await apiGet<PaginatedResponse<ApiBudgetTemplate>>('/budget-templates/')
        this.templates = templates.results
        this.activeTemplateId = this.activeTemplateId || templates.results[0]?.id || ''
        await this.loadTemplateFields()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载模板失败'
      } finally {
        this.loading = false
      }
    },
    async createTemplateField() {
      if (!this.activeTemplateId) {
        this.error = '当前没有可编辑模板'
        return
      }
      const code = this.templateFieldDraft.code.trim()
      const label = this.templateFieldDraft.label.trim()
      if (!code || !label) {
        this.error = '字段编码和显示名称必填'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        const nextOrder = Math.max(0, ...this.templateFields.map((field) => field.order)) + 10
        await apiPost('/template-fields/', {
          template: this.activeTemplateId,
          code,
          label,
          data_type: this.templateFieldDraft.dataType,
          input_type: inputTypeForDataType(this.templateFieldDraft.dataType),
          required: this.templateFieldDraft.required,
          order: nextOrder,
          width: 160,
        })
        this.templateFieldDraft = { code: '', label: '', dataType: 'text', required: false }
        await this.loadTemplateFields()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '新增模板字段失败'
      } finally {
        this.actionLoading = false
      }
    },
    async updateTemplateField(field: ApiTemplateField, patch: Partial<Pick<ApiTemplateField, 'label' | 'required'>>) {
      this.actionLoading = true
      this.error = ''
      try {
        await apiPatch(`/template-fields/${field.id}/`, patch)
        await this.loadTemplateFields()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '更新模板字段失败'
      } finally {
        this.actionLoading = false
      }
    },
    async deleteTemplateField(field: ApiTemplateField) {
      this.actionLoading = true
      this.error = ''
      try {
        await apiDelete(`/template-fields/${field.id}/`)
        await this.loadTemplateFields()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '删除模板字段失败'
      } finally {
        this.actionLoading = false
      }
    },
    defaultDynamicData() {
      return Object.fromEntries(
        this.templateFields
          .filter((field) => field.required)
          .map((field) => [field.code, defaultValueForField(field)]),
      )
    },
    async renameLine(line: BudgetLinePreview) {
      if (!line.id || line.locked || line.versionId !== this.activeDraftVersionId) {
        this.error = '只能编辑当前 Draft 版本的预算条目'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        await apiPatch(`/budget-lines/${line.id}/`, {
          description: `${line.description}（已更新）`,
        })
        await this.load()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '更新预算条目失败'
      } finally {
        this.actionLoading = false
      }
    },
    async updateDynamicField(line: BudgetLinePreview, field: ApiTemplateField, value: unknown) {
      if (!line.id || line.locked || line.versionId !== this.activeDraftVersionId) {
        this.error = '只能编辑当前 Draft 版本的动态字段'
        return
      }
      this.actionLoading = true
      this.error = ''
      this.fieldErrors = {}
      try {
        await apiPatch(`/budget-lines/${line.id}/`, {
          dynamic_data: { [field.code]: normalizeDynamicValue(field, value) },
        })
        await this.load()
      } catch (error) {
        const message = error instanceof Error ? error.message : '更新动态字段失败'
        this.error = message
        this.fieldErrors[`${line.id}:${field.code}`] = message
      } finally {
        this.actionLoading = false
      }
    },
    async loadMasterData() {
      this.loading = true
      this.error = ''
      try {
        const [categories, projects, vendors, regions] = await Promise.all([
          apiGet<PaginatedResponse<ApiCategory>>('/categories/'),
          apiGet<PaginatedResponse<ApiProject>>('/projects/'),
          apiGet<PaginatedResponse<ApiNamedMasterData>>('/vendors/'),
          apiGet<PaginatedResponse<ApiNamedMasterData>>('/regions/'),
        ])
        this.masterData.categories = categories.results
        this.masterData.projects = projects.results
        this.masterData.vendors = vendors.results
        this.masterData.regions = regions.results
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载主数据失败'
      } finally {
        this.loading = false
      }
    },
    async createMasterData() {
      const code = this.masterDataDraft.code.trim()
      const name = this.masterDataDraft.name.trim()
      if (!code || !name) {
        this.error = '编码和名称必填'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        await apiPost(`/${this.masterDataKind}/`, {
          code,
          name,
          level: this.masterDataKind === 'categories' ? 'category' : undefined,
          is_active: true,
          sort_order: 0,
        })
        this.masterDataDraft = { code: '', name: '' }
        await this.loadMasterData()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '新增主数据失败'
      } finally {
        this.actionLoading = false
      }
    },
  },
})

function normalizeDynamicValue(field: ApiTemplateField, value: unknown) {
  if (field.data_type === 'boolean') return Boolean(value)
  if (value === null || value === undefined) return ''
  return String(value)
}

function inputTypeForDataType(dataType: ApiTemplateField['data_type']) {
  if (dataType === 'money' || dataType === 'number') return 'number'
  if (dataType === 'date') return 'date'
  return 'text'
}

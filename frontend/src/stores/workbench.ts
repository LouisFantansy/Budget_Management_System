import { defineStore } from 'pinia'
import { apiDelete, apiGet, apiGetText, apiPatch, apiPost, type PaginatedResponse } from '../api/client'
import type {
  ApiApprovalRequest,
  ApiAllocationUpload,
  ApiBudgetBook,
  ApiBudgetCycle,
  ApiDashboardDrilldown,
  ApiDashboardApplyResponse,
  ApiDashboardConfig,
  ApiDepartment,
  ApiBudgetLine,
  ApiBudgetLineBulkResult,
  ApiBudgetTask,
  ApiBudgetOverview,
  ApiBudgetTemplate,
  ApiBudgetVersion,
  ApiCategory,
  ApiImportJob,
  ApiImportJobErrors,
  ApiNotification,
  ApiNotificationSummary,
  ApiPrimarySyncStatus,
  ApiTemplateField,
  ApiUser,
  ApiNamedMasterData,
  ApiProject,
  ApiPurchaseHistory,
  ApiVersionDiff,
  ApprovalItem,
  BudgetLinePreview,
  BudgetTask,
  DashboardDrilldownDimension,
  DashboardScope,
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
    budget_version: '审批版拉取',
  }
  return labels[source] ?? source
}

function defaultValueForField(field: ApiTemplateField) {
  if (field.input_type === 'formula') return ''
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
    activeCycleId: '',
    departments: [] as ApiDepartment[],
    loginForm: {
      username: 'primary-admin',
      password: 'password',
    },
    activeDraftVersionId: '',
    activeBookId: '',
    activeDraftDepartmentId: '',
    activeSourceType: '',
    activeTemplateId: '',
    selectedLineId: '',
    selectedLineIds: [] as string[],
    bulkEditDraft: {
      reason: '',
      purchaseReason: '',
      comment: '',
    },
    revisionSourceBookId: '',
    versionDiff: null as ApiVersionDiff | null,
    budgetOverview: null as ApiBudgetOverview | null,
    dashboardExpenseType: '' as '' | 'opex' | 'capex',
    dashboardDrilldown: null as ApiDashboardDrilldown | null,
    dashboardDrilldownLoading: false,
    dashboardConfigs: [] as ApiDashboardConfig[],
    activeDashboardConfigId: '',
    dashboardFocusDepartmentId: '',
    dashboardConfigDraft: {
      name: '',
      scope: 'personal' as DashboardScope,
      departmentId: '',
      isDefault: true,
    },
    templateFields: [] as ApiTemplateField[],
    importJobs: [] as ApiImportJob[],
    latestImportJob: null as ApiImportJob | null,
    importJobErrors: null as ApiImportJobErrors | null,
    notifications: [] as ApiNotification[],
    notificationSummary: {
      total: 0,
      unread_count: 0,
      latest_unread_title: '',
    } as ApiNotificationSummary,
    latestAllocationUpload: null as ApiAllocationUpload | null,
    primarySyncStatus: null as ApiPrimarySyncStatus | null,
    allocationDraft: {
      sourceName: 'group-allocation.tsv',
      rawText: '',
    },
    importDraft: {
      sourceName: 'budget-import.tsv',
      mode: 'append' as ApiImportJob['mode'],
      rawText: '',
    },
    templates: [] as ApiBudgetTemplate[],
    templateFieldDraft: {
      code: '',
      label: '',
      dataType: 'text' as ApiTemplateField['data_type'],
      inputType: 'text' as ApiTemplateField['input_type'],
      formula: '',
      required: false,
      primaryVisibleOnly: false,
      primaryEditableOnly: false,
      width: 160,
      frozen: false,
      optionSource: '',
      dashboardEnabled: false,
      approvalIncluded: true,
      importAliases: '',
    },
    masterDataKind: 'categories' as MasterDataKind,
    masterDataDraft: {
      code: '',
      name: '',
      projectCategoryId: '',
      productLineId: '',
    },
    masterData: {
      categories: [] as ApiCategory[],
      'project-categories': [] as ApiNamedMasterData[],
      'product-lines': [] as ApiNamedMasterData[],
      projects: [] as ApiProject[],
      vendors: [] as ApiNamedMasterData[],
      regions: [] as ApiNamedMasterData[],
    },
    fieldErrors: {} as Record<string, string>,
    lineErrors: {} as Record<string, string>,
    recommendations: {} as Record<string, ApiPurchaseHistory[]>,
    cycleName: '2027 年度预算编制',
    cycleStatus: '',
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
    async loadDepartments() {
      const response = await apiGet<PaginatedResponse<ApiDepartment>>('/departments/')
      this.departments = response.results
      response.results.forEach((item) => {
        departmentNames[item.id] = item.name
      })
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const [cycles, departments, categories, projects, books, tasks, approvals] = await Promise.all([
          apiGet<PaginatedResponse<ApiBudgetCycle>>('/cycles/'),
          apiGet<PaginatedResponse<ApiDepartment>>('/departments/'),
          apiGet<PaginatedResponse<{ id: string; name: string }>>('/categories/'),
          apiGet<PaginatedResponse<{ id: string; name: string }>>('/projects/'),
          apiGet<PaginatedResponse<ApiBudgetBook>>('/budget-books/'),
          apiGet<PaginatedResponse<ApiBudgetTask>>('/budget-tasks/'),
          apiGet<PaginatedResponse<ApiApprovalRequest>>('/approval-requests/'),
        ])

        const activeCycle = cycles.results[0]
        this.activeCycleId = activeCycle?.id ?? ''
        this.cycleName = activeCycle?.name ?? '未配置预算周期'
        this.cycleStatus = activeCycle?.status_label ?? activeCycle?.status ?? ''

        this.departments = departments.results
        departments.results.forEach((item) => {
          departmentNames[item.id] = item.name
        })
        categories.results.forEach((item) => {
          categoryNames[item.id] = item.name
        })
        projects.results.forEach((item) => {
          projectNames[item.id] = item.name
        })

        this.tasks = tasks.results.map((task) => ({
          id: task.id,
          cycleId: task.cycle,
          bookId: task.book_id || undefined,
          currentDraftId: task.current_draft_id || null,
          departmentId: task.department,
          sourceType: task.source_type || undefined,
          templateId: task.template_id || undefined,
          expenseType: task.expense_type || undefined,
          dueAt: task.due_at || undefined,
          department: task.department_name || departmentNames[task.department] || task.department,
          owner: task.owner_name || '未分配',
          status: task.status_label || task.status,
          version: task.version_label || '未开始',
          amount: money(task.amount || 0),
        }))

        this.approvals = approvals.results.map((item) => ({
          id: item.id,
          title: item.title,
          department: departmentNames[item.department] ?? item.department,
          versionContext: item.dashboard_context.version_context ?? 'submitted_version',
          amount: '待审批',
          due: item.status === 'pending' ? '待处理' : item.status,
          stage: item.current_stage_label || item.current_stage || '',
          diffSummary: item.diff_summary ?? null,
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
            lineNo: line.line_no,
            versionId: line.version,
            departmentId: line.department,
            editableBySecondary: line.editable_by_secondary,
            sourceDepartmentCode:
              typeof line.admin_annotations?.source_department === 'string'
                ? String(line.admin_annotations.source_department)
                : undefined,
            adminAnnotations: line.admin_annotations,
            monthlyPlans: line.monthly_plans,
            dynamicData: line.dynamic_data,
            fieldPermissions: line.field_permissions ?? {},
            unitPrice: line.unit_price,
            totalQuantity: line.total_quantity,
            totalAmount: line.total_amount,
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
        const activeBook =
          books.results.find((book) => book.id === this.activeBookId) ??
          books.results.find((book) => book.current_draft === this.activeDraftVersionId) ??
          books.results.find((book) => book.current_draft) ??
          books.results[0]
        this.applyActiveBookContext(activeBook, books.results[0]?.template ?? '')
        this.revisionSourceBookId = books.results.find((book) => !book.current_draft && book.latest_approved_version)?.id ?? ''
        const primaryConsolidatedBook = books.results.find((book) => book.source_type === 'primary_consolidated')
        await this.loadPrimarySyncStatus(primaryConsolidatedBook?.id)
        await this.loadTemplateFields()
        await this.loadImportJobs()
        await this.loadNotificationSummary()
        this.syncSelectedLine()

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
        await this.loadNotificationSummary()
      } catch {
        this.currentUser = null
        this.notificationSummary = { total: 0, unread_count: 0, latest_unread_title: '' }
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
        this.notifications = []
        this.notificationSummary = { total: 0, unread_count: 0, latest_unread_title: '' }
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
        const nextLineNo =
          Math.max(
            0,
            ...this.budgetLines
              .filter((line) => line.versionId === this.activeDraftVersionId)
              .map((line) => Number(line.lineNo ?? 0)),
          ) + 1
        await apiPost('/budget-lines/', {
          version: this.activeDraftVersionId,
          department: this.activeDraftDepartmentId,
          line_no: nextLineNo,
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
      this.fieldErrors = {}
      this.lineErrors = {}
      try {
        await apiPost(`/budget-versions/${this.activeDraftVersionId}/submit/`)
        await this.load()
      } catch (error) {
        const message = error instanceof Error ? error.message : '提交送审失败'
        this.error = message
        this.captureLineValidationErrors(message)
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
    async pullPrimaryConsolidated(expenseType: 'opex' | 'capex' = 'opex') {
      this.actionLoading = true
      this.error = ''
      try {
        if (!this.activeCycleId) {
          this.error = '当前没有预算周期'
          return
        }
        await apiPost(`/cycles/${this.activeCycleId}/pull-primary-consolidated/`, { expense_type: expenseType })
        await this.load()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '拉取一级总表失败'
      } finally {
        this.actionLoading = false
      }
    },
    async distributeCycleTasks() {
      if (!this.activeCycleId) {
        this.error = '当前没有预算周期'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        await apiPost(`/cycles/${this.activeCycleId}/distribute-tasks/`, {})
        await this.load()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '分发预算任务失败'
      } finally {
        this.actionLoading = false
      }
    },
    async downloadGroupAllocationTemplate() {
      this.actionLoading = true
      this.error = ''
      try {
        if (!this.activeCycleId) {
          this.error = '当前没有预算周期'
          return
        }
        const content = await apiGetText(`/cycles/${this.activeCycleId}/group-allocation-template/`)
        const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `group-allocation-${this.activeCycleId}.csv`
        document.body.appendChild(link)
        link.click()
        link.remove()
        window.URL.revokeObjectURL(url)
      } catch (error) {
        this.error = error instanceof Error ? error.message : '下载集团分摊模板失败'
      } finally {
        this.actionLoading = false
      }
    },
    async importGroupAllocation() {
      if (!this.allocationDraft.rawText.trim()) {
        this.error = '请粘贴集团分摊数据后再导入'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        if (!this.activeCycleId) {
          this.error = '当前没有预算周期'
          return
        }
        this.latestAllocationUpload = await apiPost<ApiAllocationUpload>(`/cycles/${this.activeCycleId}/import-group-allocation/`, {
          source_name: this.allocationDraft.sourceName,
          raw_text: this.allocationDraft.rawText,
        })
        if (this.latestAllocationUpload.status === 'failed') {
          this.error = this.latestAllocationUpload.summary.message ?? '集团分摊导入失败'
          return
        }
        this.allocationDraft.rawText = ''
        await this.load()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '导入集团分摊失败'
      } finally {
        this.actionLoading = false
      }
    },
    async selectDraftContext(task: BudgetTask) {
      if (!task.currentDraftId || !task.bookId) {
        this.error = '当前任务没有可查看的 Draft 版本'
        return false
      }
      const selectedLine = this.budgetLines.find((line) => line.versionId === task.currentDraftId)
      this.activeBookId = task.bookId
      this.activeDraftVersionId = task.currentDraftId
      this.activeDraftDepartmentId = task.departmentId ?? selectedLine?.departmentId ?? ''
      this.activeSourceType = task.sourceType ?? ''
      this.activeTemplateId = task.templateId ?? this.activeTemplateId
      this.error = ''
      await this.loadTemplateFields()
      await this.loadImportJobs()
      this.syncSelectedLine()
      return true
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
        if (!this.departments.length) {
          await this.loadDepartments()
        }
        this.versionContext = context
        const query = new URLSearchParams({ version_context: context })
        if (this.dashboardExpenseType) {
          query.set('expense_type', this.dashboardExpenseType)
        }
        if (this.dashboardFocusDepartmentId) {
          query.set('focus_department_id', this.dashboardFocusDepartmentId)
        }
        this.budgetOverview = await apiGet<ApiBudgetOverview>(`/dashboard-configs/budget-overview/?${query.toString()}`)
        this.dashboardDrilldown = null
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载预算看板失败'
      } finally {
        this.loading = false
      }
    },
    async loadDashboardConfigs() {
      this.loading = true
      this.error = ''
      try {
        if (!this.departments.length) {
          await this.loadDepartments()
        }
        const response = await apiGet<PaginatedResponse<ApiDashboardConfig>>('/dashboard-configs/')
        this.dashboardConfigs = response.results
        const defaultConfig = response.results.find((item) => item.is_default)
        if (defaultConfig) {
          this.activeDashboardConfigId = defaultConfig.id
        }
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载看板配置失败'
      } finally {
        this.loading = false
      }
    },
    async saveDashboardConfig() {
      const name = this.dashboardConfigDraft.name.trim()
      if (!name) {
        this.error = '看板配置名称必填'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        await apiPost<ApiDashboardConfig>('/dashboard-configs/', {
          name,
          scope: this.dashboardConfigDraft.scope,
          department: this.dashboardConfigDraft.scope === 'department' ? this.dashboardConfigDraft.departmentId || null : null,
          version_context: this.versionContext === 'current_draft' ? 'current_draft' : 'latest_approved',
          config: {
            focus_department_id: this.dashboardFocusDepartmentId || null,
            expense_type: this.dashboardExpenseType || null,
          },
          is_default: this.dashboardConfigDraft.isDefault,
        })
        this.dashboardConfigDraft = { name: '', scope: 'personal', departmentId: '', isDefault: true }
        await this.loadDashboardConfigs()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '保存看板配置失败'
      } finally {
        this.actionLoading = false
      }
    },
    async applyDashboardConfig(configId: string) {
      this.loading = true
      this.error = ''
      try {
        const response = await apiGet<ApiDashboardApplyResponse>(`/dashboard-configs/${configId}/apply/`)
        this.activeDashboardConfigId = response.config.id
        this.versionContext = response.config.version_context
        this.dashboardFocusDepartmentId = response.config.config.focus_department_id ?? ''
        this.dashboardExpenseType = response.config.config.expense_type ?? ''
        this.budgetOverview = response.overview
        this.dashboardDrilldown = null
      } catch (error) {
        this.error = error instanceof Error ? error.message : '应用看板配置失败'
      } finally {
        this.loading = false
      }
    },
    async loadDashboardDrilldown(dimension: DashboardDrilldownDimension, value: string) {
      this.dashboardDrilldownLoading = true
      this.error = ''
      try {
        const query = new URLSearchParams({
          version_context: this.versionContext === 'current_draft' ? 'current_draft' : 'latest_approved',
          dimension,
          value,
        })
        if (this.dashboardExpenseType) {
          query.set('expense_type', this.dashboardExpenseType)
        }
        if (this.dashboardFocusDepartmentId) {
          query.set('focus_department_id', this.dashboardFocusDepartmentId)
        }
        this.dashboardDrilldown = await apiGet<ApiDashboardDrilldown>(`/dashboard-configs/budget-drilldown/?${query.toString()}`)
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载看板下钻失败'
      } finally {
        this.dashboardDrilldownLoading = false
      }
    },
    clearDashboardDrilldown() {
      this.dashboardDrilldown = null
    },
    async loadTemplateFields() {
      if (!this.activeTemplateId) {
        this.templateFields = []
        return
      }
      const fields = await apiGet<PaginatedResponse<ApiTemplateField>>(`/template-fields/?template=${this.activeTemplateId}`)
      this.templateFields = fields.results.sort((left, right) => left.order - right.order)
    },
    async loadImportJobs() {
      if (!this.activeDraftVersionId) {
        this.importJobs = []
        this.latestImportJob = null
        return
      }
      try {
        const response = await apiGet<PaginatedResponse<ApiImportJob>>(`/import-jobs/?version=${this.activeDraftVersionId}`)
        this.importJobs = response.results
        this.latestImportJob = response.results[0] ?? null
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载导入任务失败'
      }
    },
    async importBudgetLines() {
      if (!this.activeDraftVersionId) {
        this.error = '当前没有可导入的 Draft 版本'
        return
      }
      if (!this.importDraft.rawText.trim()) {
        this.error = '请粘贴 Excel/CSV 内容后再导入'
        return
      }
      this.actionLoading = true
      this.error = ''
      this.importJobErrors = null
      try {
        const job = await apiPost<ApiImportJob>('/import-jobs/', {
          version: this.activeDraftVersionId,
          source_name: this.importDraft.sourceName,
          mode: this.importDraft.mode,
          raw_text: this.importDraft.rawText,
        })
        this.latestImportJob = job
        await this.loadImportJobs()
        if (job.status === 'failed') {
          await this.loadImportJobErrors(job.id)
          this.error = job.summary.message ?? '导入失败'
          return
        }
        this.importDraft.rawText = ''
        await this.load()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '导入预算条目失败'
      } finally {
        this.actionLoading = false
      }
    },
    async loadImportJobErrors(jobId: string) {
      try {
        this.importJobErrors = await apiGet<ApiImportJobErrors>(`/import-jobs/${jobId}/errors/`)
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载导入错误失败'
      }
    },
    async exportActiveDraftCsv() {
      if (!this.activeDraftVersionId) {
        this.error = '当前没有可导出的 Draft 版本'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        const content = await apiGetText(`/budget-versions/${this.activeDraftVersionId}/export-csv/`)
        const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `budget-version-${this.activeDraftVersionId}.csv`
        document.body.appendChild(link)
        link.click()
        link.remove()
        window.URL.revokeObjectURL(url)
      } catch (error) {
        this.error = error instanceof Error ? error.message : '导出预算条目失败'
      } finally {
        this.actionLoading = false
      }
    },
    async downloadImportTemplate() {
      if (!this.activeDraftVersionId) {
        this.error = '当前没有可下载模板的 Draft 版本'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        const content = await apiGetText(`/budget-versions/${this.activeDraftVersionId}/import-template/`)
        const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `budget-version-${this.activeDraftVersionId}-import-template.csv`
        document.body.appendChild(link)
        link.click()
        link.remove()
        window.URL.revokeObjectURL(url)
      } catch (error) {
        this.error = error instanceof Error ? error.message : '下载导入模板失败'
      } finally {
        this.actionLoading = false
      }
    },
    async downloadImportSample() {
      if (!this.activeDraftVersionId) {
        this.error = '当前没有可下载示例的 Draft 版本'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        const content = await apiGetText(`/budget-versions/${this.activeDraftVersionId}/import-sample/`)
        const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `budget-version-${this.activeDraftVersionId}-import-sample.csv`
        document.body.appendChild(link)
        link.click()
        link.remove()
        window.URL.revokeObjectURL(url)
      } catch (error) {
        this.error = error instanceof Error ? error.message : '下载示例数据失败'
      } finally {
        this.actionLoading = false
      }
    },
    async loadNotifications() {
      if (!this.currentUser) {
        this.notifications = []
        return
      }
      this.loading = true
      this.error = ''
      try {
        const response = await apiGet<PaginatedResponse<ApiNotification>>('/notifications/')
        this.notifications = response.results
        await this.loadNotificationSummary()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载通知失败'
      } finally {
        this.loading = false
      }
    },
    async loadNotificationSummary() {
      if (!this.currentUser) {
        this.notificationSummary = { total: 0, unread_count: 0, latest_unread_title: '' }
        return
      }
      try {
        this.notificationSummary = await apiGet<ApiNotificationSummary>('/notifications/summary/')
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载通知摘要失败'
      }
    },
    async loadPrimarySyncStatus(bookId?: string) {
      if (!bookId) {
        this.primarySyncStatus = null
        return
      }
      try {
        this.primarySyncStatus = await apiGet<ApiPrimarySyncStatus>(`/budget-books/${bookId}/sync-status/`)
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载一级总表同步状态失败'
      }
    },
    async markNotificationsRead(ids?: string[]) {
      if (!this.currentUser) return
      this.actionLoading = true
      this.error = ''
      try {
        if (ids?.length) {
          await apiPost('/notifications/mark-read/', { ids })
        } else {
          await apiPost('/notifications/mark-read/', { all: true })
        }
        await this.loadNotifications()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '标记通知已读失败'
      } finally {
        this.actionLoading = false
      }
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
          input_type: this.templateFieldDraft.inputType,
          formula: this.templateFieldDraft.inputType === 'formula' ? this.templateFieldDraft.formula.trim() : '',
          required: this.templateFieldDraft.required,
          visible_rules: this.templateFieldDraft.primaryVisibleOnly ? { visible_to: ['primary'] } : {},
          editable_rules: this.templateFieldDraft.primaryEditableOnly ? { editable_by: ['primary'] } : {},
          order: nextOrder,
          width: this.templateFieldDraft.width,
          frozen: this.templateFieldDraft.frozen,
          option_source: this.templateFieldDraft.optionSource.trim(),
          approval_included: this.templateFieldDraft.approvalIncluded,
          dashboard_enabled: this.templateFieldDraft.dashboardEnabled,
          import_aliases: this.templateFieldDraft.importAliases
            .split(/[\n,]/)
            .map((item) => item.trim())
            .filter(Boolean),
        })
        this.templateFieldDraft = {
          code: '',
          label: '',
          dataType: 'text',
          inputType: 'text',
          formula: '',
          required: false,
          primaryVisibleOnly: false,
          primaryEditableOnly: false,
          width: 160,
          frozen: false,
          optionSource: '',
          dashboardEnabled: false,
          approvalIncluded: true,
          importAliases: '',
        }
        await this.loadTemplateFields()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '新增模板字段失败'
      } finally {
        this.actionLoading = false
      }
    },
    async updateTemplateField(
      field: ApiTemplateField,
      patch: Partial<
        Pick<
          ApiTemplateField,
          | 'label'
          | 'required'
          | 'visible_rules'
          | 'editable_rules'
          | 'width'
          | 'frozen'
          | 'option_source'
          | 'dashboard_enabled'
          | 'approval_included'
          | 'import_aliases'
        >
      >,
    ) {
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
    async createTemplateRevision() {
      if (!this.activeTemplateId) {
        this.error = '当前没有可复制模板'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        const revision = await apiPost<ApiBudgetTemplate>(`/budget-templates/${this.activeTemplateId}/create-revision/`, {})
        this.templates = [revision, ...this.templates.filter((item) => item.id !== revision.id)]
        this.activeTemplateId = revision.id
        await this.loadTemplateFields()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '创建模板修订失败'
      } finally {
        this.actionLoading = false
      }
    },
    async bootstrapTemplatesFromPrevious(cycleId: string) {
      this.actionLoading = true
      this.error = ''
      try {
        await apiPost('/budget-templates/bootstrap-from-previous/', { cycle: cycleId })
        await this.loadTemplates()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '复制上一周期模板失败'
      } finally {
        this.actionLoading = false
      }
    },
    defaultDynamicData() {
      return Object.fromEntries(
        this.templateFields
          .filter((field) => field.required && field.user_permissions?.editable !== false)
          .map((field) => [field.code, defaultValueForField(field)]),
      )
    },
    selectLine(lineId?: string) {
      this.selectedLineId = lineId ?? ''
    },
    toggleLineSelection(lineId?: string) {
      if (!lineId) return
      if (this.selectedLineIds.includes(lineId)) {
        this.selectedLineIds = this.selectedLineIds.filter((item) => item !== lineId)
        return
      }
      this.selectedLineIds = [...this.selectedLineIds, lineId]
    },
    selectAllActiveLines() {
      this.selectedLineIds = this.budgetLines
        .filter((line) => line.versionId === this.activeDraftVersionId && this.canEditLine(line))
        .map((line) => line.id)
        .filter((lineId): lineId is string => Boolean(lineId))
    },
    clearLineSelection() {
      this.selectedLineIds = []
    },
    isLineSelected(lineId?: string) {
      return !!lineId && this.selectedLineIds.includes(lineId)
    },
    canEditLine(line: BudgetLinePreview) {
      if (!line.id || line.versionId !== this.activeDraftVersionId) {
        return false
      }
      if (this.activeSourceType === 'primary_consolidated') {
        return true
      }
      return line.editableBySecondary !== false
    },
    async renameLine(line: BudgetLinePreview) {
      if (!this.canEditLine(line)) {
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
      if (!this.canEditLine(line) || !this.canEditDynamicField(line, field)) {
        this.error = '只能编辑当前 Draft 版本的动态字段'
        return
      }
      this.actionLoading = true
      this.error = ''
      this.fieldErrors = {}
      this.lineErrors = {}
      try {
        await apiPatch(`/budget-lines/${line.id}/`, {
          dynamic_data: { [field.code]: normalizeDynamicValue(field, value) },
        })
        await this.load()
      } catch (error) {
        const message = error instanceof Error ? error.message : '更新动态字段失败'
        this.error = message
        const payload = extractJsonPayload(message)
        const fieldMessage = payload?.dynamic_data?.[field.code]
        this.fieldErrors[`${line.id}:${field.code}`] = typeof fieldMessage === 'string' ? fieldMessage : message
      } finally {
        this.actionLoading = false
      }
    },
    canEditDynamicField(line: BudgetLinePreview, field: ApiTemplateField) {
      if (!this.canEditLine(line)) return false
      return line.fieldPermissions?.[field.code]?.editable !== false && field.input_type !== 'formula'
    },
    async loadRecommendations(line: BudgetLinePreview) {
      if (!line.id || !line.description.trim()) return
      this.error = ''
      try {
        this.recommendations[line.id] = await apiGet<ApiPurchaseHistory[]>(
          `/purchase-history/suggest/?q=${encodeURIComponent(line.description)}`,
        )
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载推荐价失败'
      }
    },
    async applyRecommendedPrice(line: BudgetLinePreview, price: string) {
      if (!this.canEditLine(line)) {
        this.error = '只能对当前 Draft 版本应用推荐价'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        await apiPatch(`/budget-lines/${line.id}/`, { unit_price: price })
        await this.load()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '应用推荐价失败'
      } finally {
        this.actionLoading = false
      }
    },
    async bulkDeleteLines() {
      if (!this.selectedLineIds.length) {
        this.error = '请先选择要删除的预算条目'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        await apiPost<ApiBudgetLineBulkResult>('/budget-lines/bulk/', {
          action: 'delete',
          line_ids: this.selectedLineIds,
        })
        this.clearLineSelection()
        await this.load()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '批量删除失败'
      } finally {
        this.actionLoading = false
      }
    },
    async bulkDuplicateLines() {
      if (!this.selectedLineIds.length) {
        this.error = '请先选择要复制的预算条目'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        await apiPost<ApiBudgetLineBulkResult>('/budget-lines/bulk/', {
          action: 'duplicate',
          line_ids: this.selectedLineIds,
        })
        await this.load()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '批量复制失败'
      } finally {
        this.actionLoading = false
      }
    },
    async bulkPatchLines() {
      if (!this.selectedLineIds.length) {
        this.error = '请先选择要批量修改的预算条目'
        return
      }
      const patch: Record<string, unknown> = {}
      if (this.bulkEditDraft.reason.trim()) {
        patch.reason = this.bulkEditDraft.reason.trim()
      }
      if (this.bulkEditDraft.purchaseReason.trim()) {
        patch.dynamic_data = { purchase_reason: this.bulkEditDraft.purchaseReason.trim() }
      }
      if (this.bulkEditDraft.comment.trim()) {
        patch.local_comments = { batch_comment: this.bulkEditDraft.comment.trim() }
      }
      if (!Object.keys(patch).length) {
        this.error = '请至少填写一个批量更新字段'
        return
      }
      this.actionLoading = true
      this.error = ''
      try {
        await apiPost<ApiBudgetLineBulkResult>('/budget-lines/bulk/', {
          action: 'patch',
          line_ids: this.selectedLineIds,
          patch,
        })
        this.bulkEditDraft = { reason: '', purchaseReason: '', comment: '' }
        await this.load()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '批量更新失败'
      } finally {
        this.actionLoading = false
      }
    },
    async loadMasterData() {
      this.loading = true
      this.error = ''
      try {
        const [categories, projectCategories, productLines, projects, vendors, regions] = await Promise.all([
          apiGet<PaginatedResponse<ApiCategory>>('/categories/'),
          apiGet<PaginatedResponse<ApiNamedMasterData>>('/project-categories/'),
          apiGet<PaginatedResponse<ApiNamedMasterData>>('/product-lines/'),
          apiGet<PaginatedResponse<ApiProject>>('/projects/'),
          apiGet<PaginatedResponse<ApiNamedMasterData>>('/vendors/'),
          apiGet<PaginatedResponse<ApiNamedMasterData>>('/regions/'),
        ])
        this.masterData.categories = categories.results
        this.masterData['project-categories'] = projectCategories.results
        this.masterData['product-lines'] = productLines.results
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
          project_category: this.masterDataKind === 'projects' ? this.masterDataDraft.projectCategoryId || null : undefined,
          product_line: this.masterDataKind === 'projects' ? this.masterDataDraft.productLineId || null : undefined,
          level: this.masterDataKind === 'categories' ? 'category' : undefined,
          is_active: true,
          sort_order: 0,
        })
        this.masterDataDraft = { code: '', name: '', projectCategoryId: '', productLineId: '' }
        await this.loadMasterData()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '新增主数据失败'
      } finally {
        this.actionLoading = false
      }
    },
    async updateMasterData(
      kind: MasterDataKind,
      itemId: string,
      patch: Record<string, unknown>,
    ) {
      this.actionLoading = true
      this.error = ''
      try {
        await apiPatch(`/${kind}/${itemId}/`, patch)
        await this.loadMasterData()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '更新主数据失败'
      } finally {
        this.actionLoading = false
      }
    },
    async deleteMasterData(kind: MasterDataKind, itemId: string) {
      this.actionLoading = true
      this.error = ''
      try {
        await apiDelete(`/${kind}/${itemId}/`)
        await this.loadMasterData()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '删除主数据失败'
      } finally {
        this.actionLoading = false
      }
    },
    captureLineValidationErrors(message: string) {
      const payload = extractJsonPayload(message)
      const lines = payload?.lines as Record<string, { budget_no?: string; dynamic_data?: Record<string, string> }> | undefined
      if (!lines) return
      Object.entries(lines).forEach(([lineId, lineError]) => {
        const fieldEntries = Object.entries(lineError.dynamic_data ?? {})
        if (fieldEntries.length) {
          this.lineErrors[lineId] = `${lineError.budget_no ?? '未命名条目'} 缺少必填字段`
        }
        fieldEntries.forEach(([fieldCode, fieldMessage]) => {
          this.fieldErrors[`${lineId}:${fieldCode}`] = String(fieldMessage)
        })
      })
    },
    applyActiveBookContext(book: ApiBudgetBook | undefined, fallbackTemplateId = '') {
      this.activeBookId = book?.id ?? ''
      this.activeDraftVersionId = book?.current_draft ?? ''
      this.activeDraftDepartmentId = book?.department ?? ''
      this.activeSourceType = book?.source_type ?? ''
      this.activeTemplateId = book?.template ?? fallbackTemplateId
    },
    syncSelectedLine() {
      const activeLines = this.budgetLines.filter((line) => line.versionId === this.activeDraftVersionId)
      if (activeLines.some((line) => line.id === this.selectedLineId)) {
        this.selectedLineIds = this.selectedLineIds.filter((lineId) =>
          activeLines.some((line) => line.id === lineId && this.canEditLine(line)),
        )
        return
      }
      this.selectedLineId = activeLines[0]?.id ?? ''
      this.selectedLineIds = this.selectedLineIds.filter((lineId) =>
        activeLines.some((line) => line.id === lineId && this.canEditLine(line)),
      )
    },
  },
})

function normalizeDynamicValue(field: ApiTemplateField, value: unknown) {
  if (field.data_type === 'boolean') return Boolean(value)
  if (value === null || value === undefined) return ''
  return String(value)
}

function extractJsonPayload(message: string) {
  const jsonStart = message.indexOf('{')
  if (jsonStart < 0) return null
  try {
    return JSON.parse(message.slice(jsonStart))
  } catch {
    return null
  }
}

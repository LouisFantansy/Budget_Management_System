export type VersionContext = 'latest_approved' | 'current_draft' | 'submitted_version'
export type DashboardVersionContext = 'latest_approved' | 'current_draft'
export type DashboardScope = 'personal' | 'department' | 'global'

export interface SummaryStat {
  label: string
  value: string
  delta: string
  tone: 'blue' | 'green' | 'amber' | 'red'
}

export interface BudgetTask {
  bookId?: string
  currentDraftId?: string | null
  departmentId?: string
  sourceType?: string
  templateId?: string
  department: string
  owner: string
  status: string
  version: string
  amount: string
}

export interface BudgetMonthlyPlanPreview {
  month: number
  quantity: string
  amount: string
}

export interface ApprovalItem {
  id?: string
  title: string
  department: string
  versionContext: VersionContext
  amount: string
  due: string
  diffSummary?: {
    added: number
    deleted: number
    modified: number
    total_changes: number
  } | null
}

export interface BudgetLinePreview {
  id?: string
  lineNo?: number
  versionId?: string
  departmentId?: string
  editableBySecondary?: boolean
  sourceDepartmentCode?: string
  adminAnnotations?: Record<string, unknown>
  monthlyPlans?: BudgetMonthlyPlanPreview[]
  dynamicData?: Record<string, unknown>
  unitPrice?: string
  totalQuantity?: string
  totalAmount?: string
  budgetNo: string
  description: string
  category: string
  project: string
  owner: string
  amount: string
  source: string
  locked: boolean
}

export interface ApiBudgetBook {
  id: string
  department: string
  expense_type: 'opex' | 'capex'
  source_type: string
  status: string
  template: string
  current_draft: string | null
  latest_approved_version: string | null
}

export interface ApiBudgetLine {
  id: string
  version: string
  line_no: number
  budget_no: string
  description: string
  category: string | null
  project: string | null
  department: string
  unit_price: string
  total_quantity: string
  total_amount: string
  dynamic_data: Record<string, unknown>
  admin_annotations: Record<string, unknown>
  source_ref_type: string
  editable_by_secondary: boolean
  monthly_plans: BudgetMonthlyPlanPreview[]
}

export interface ApiTemplateField {
  id: string
  template: string
  code: string
  label: string
  data_type: 'text' | 'number' | 'money' | 'date' | 'boolean' | 'option' | 'json'
  required: boolean
  order: number
  width: number
}

export interface ApiBudgetTemplate {
  id: string
  name: string
  expense_type: 'opex' | 'capex' | 'special'
  schema_version: number
  status: string
}

export interface ApiApprovalRequest {
  id: string
  title: string
  department: string
  status: string
  diff_summary?: {
    added: number
    deleted: number
    modified: number
    total_changes: number
  } | null
  dashboard_context: {
    version_context?: VersionContext
  }
}

export interface ApiBudgetVersion {
  id: string
  book: string
  version_no: number
  base_version: string | null
  status: string
}

export interface ApiVersionDiff {
  base_version_id: string
  target_version_id: string
  summary: {
    added: number
    deleted: number
    modified: number
    total_changes: number
  }
  changes: Array<{
    type: 'added' | 'deleted' | 'modified'
    key: string
    budget_no: string
    description: string
    amount_delta?: string
    field_changes: Array<{
      field: string
      old: string
      new: string
      delta: string
    }>
    monthly_changes: Array<{
      month: number
      old_amount: string
      new_amount: string
      amount_delta: string
    }>
  }>
}

export interface ApiBudgetOverview {
  version_context: DashboardVersionContext
  line_count: number
  total_amount: string
  by_department: Array<{
    department_id: string
    department_name: string
    line_count: number
    total_amount: string
  }>
  by_category: Array<{
    category_id: string
    category_name: string
    line_count: number
    total_amount: string
  }>
  monthly: Array<{
    month: number
    amount: string
    quantity: string
  }>
}

export interface ApiUser {
  id: number
  username: string
  display_name: string
  employee_id: string
  email: string
  primary_department: string | null
}

export interface ApiDepartment {
  id: string
  name: string
  code: string
  level: 'primary' | 'secondary' | 'section' | 'ss_public'
  parent: string | null
}

export interface ApiNamedMasterData {
  id: string
  code: string
  name: string
  is_active: boolean
  sort_order: number
}

export interface ApiCategory extends ApiNamedMasterData {
  level: 'category' | 'l1' | 'l2'
  parent: string | null
}

export interface ApiProject extends ApiNamedMasterData {
  project_category: string | null
  product_line: string | null
}

export type MasterDataKind =
  | 'categories'
  | 'project-categories'
  | 'product-lines'
  | 'projects'
  | 'vendors'
  | 'regions'

export interface ApiPurchaseHistory {
  id: string
  purchase_name: string
  deal_price: string
  recommended_price: string
  source: string
}

export interface ApiDashboardConfig {
  id: string
  name: string
  owner: number
  owner_name: string
  scope: DashboardScope
  department: string | null
  department_name: string | null
  version_context: DashboardVersionContext
  config: {
    focus_department_id?: string | null
  }
  is_default: boolean
}

export interface ApiDashboardApplyResponse {
  config: ApiDashboardConfig
  overview: ApiBudgetOverview
}

export interface ApiImportJob {
  id: string
  version: string
  requester: number | null
  requester_name: string
  source_name: string
  mode: 'append' | 'replace'
  status: 'processing' | 'success' | 'failed'
  total_rows: number
  imported_rows: number
  error_rows: number
  summary: {
    message?: string
    mode?: string
    imported_budget_nos?: string[]
  }
  errors: Array<{
    row: number
    errors: Record<string, unknown>
  }>
}

export interface ApiImportJobErrors {
  id: string
  status: 'processing' | 'success' | 'failed'
  error_rows: number
  errors: Array<{
    row: number
    errors: Record<string, unknown>
  }>
}

export interface ApiBudgetLineBulkResult {
  action: 'delete' | 'duplicate' | 'patch'
  affected: number
  created_ids?: string[]
  updated_ids?: string[]
}

export interface ApiNotification {
  id: string
  recipient: number
  category: 'approval_todo' | 'approval_result' | 'system'
  title: string
  message: string
  status: 'unread' | 'read'
  target_type: string
  target_id: string | null
  department: string | null
  extra: Record<string, unknown>
  read_at: string | null
  created_at: string
  updated_at: string
}

export interface ApiNotificationSummary {
  total: number
  unread_count: number
  latest_unread_title: string
}

export interface ApiAllocationUpload {
  id: string
  cycle: string
  requester: number | null
  requester_name: string
  source_name: string
  status: 'success' | 'failed'
  total_rows: number
  imported_rows: number
  error_rows: number
  summary: {
    message?: string
    book_id?: string
    version_id?: string
    departments?: string[]
  }
  errors: Array<{
    row: number
    errors: Record<string, unknown>
  }>
}

export interface ApiPrimarySyncStatus {
  has_updates: boolean
  line_count: number
  departments: Array<{
    department_code: string
    department_name: string
    current_source_version_id: string
    latest_approved_version_id: string
  }>
}

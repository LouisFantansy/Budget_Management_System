export type VersionContext = 'latest_approved' | 'current_draft' | 'submitted_version'

export interface SummaryStat {
  label: string
  value: string
  delta: string
  tone: 'blue' | 'green' | 'amber' | 'red'
}

export interface BudgetTask {
  bookId?: string
  currentDraftId?: string | null
  department: string
  owner: string
  status: string
  version: string
  amount: string
}

export interface ApprovalItem {
  id?: string
  title: string
  department: string
  versionContext: VersionContext
  amount: string
  due: string
}

export interface BudgetLinePreview {
  id?: string
  versionId?: string
  departmentId?: string
  dynamicData?: Record<string, unknown>
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
  budget_no: string
  description: string
  category: string | null
  project: string | null
  department: string
  total_amount: string
  dynamic_data: Record<string, unknown>
  source_ref_type: string
  editable_by_secondary: boolean
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
  version_context: VersionContext
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

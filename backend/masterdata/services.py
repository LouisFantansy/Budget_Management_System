from dataclasses import dataclass

from accounts.models import User
from orgs.models import Department

from .models import OptionSourceRegistryEntry


@dataclass(frozen=True)
class OptionSourceSpec:
    code: str
    label: str
    kind: str
    endpoint: str
    value_field: str
    label_field: str


BUILTIN_OPTION_SOURCES = [
    OptionSourceSpec('masterdata.categories', '预算分类', 'masterdata', '/categories/', 'code', 'name'),
    OptionSourceSpec('masterdata.project_categories', '项目类别', 'masterdata', '/project-categories/', 'code', 'name'),
    OptionSourceSpec('masterdata.product_lines', '产品线', 'masterdata', '/product-lines/', 'code', 'name'),
    OptionSourceSpec('masterdata.projects', '项目', 'masterdata', '/projects/', 'code', 'name'),
    OptionSourceSpec('masterdata.vendors', '供应商', 'masterdata', '/vendors/', 'code', 'name'),
    OptionSourceSpec('masterdata.regions', '地区', 'masterdata', '/regions/', 'code', 'name'),
    OptionSourceSpec('masterdata.cost_centers', '成本中心', 'masterdata', '/cost-centers/', 'code', 'name'),
    OptionSourceSpec('masterdata.gl_accounts', 'GL Account', 'masterdata', '/gl-accounts/', 'code', 'name'),
    OptionSourceSpec('masterdata.departments', '部门', 'system', '/departments/', 'code', 'name'),
    OptionSourceSpec('system.users', '用户', 'system', '/users/', 'username', 'display_name'),
]
BUILTIN_OPTION_SOURCE_MAP = {item.code: item for item in BUILTIN_OPTION_SOURCES}


def is_registered_option_source(option_source: str) -> bool:
    normalized = (option_source or '').strip()
    if not normalized:
        return False
    if normalized in BUILTIN_OPTION_SOURCE_MAP:
        return True
    return OptionSourceRegistryEntry.objects.filter(code=normalized, is_active=True).exists()


def option_source_catalog_entries():
    builtin_entries = [
        {
            'code': item.code,
            'label': item.label,
            'kind': item.kind,
            'endpoint': item.endpoint,
            'value_field': item.value_field,
            'label_field': item.label_field,
            'is_builtin': True,
        }
        for item in BUILTIN_OPTION_SOURCES
    ]
    custom_entries = list(
        OptionSourceRegistryEntry.objects.filter(is_active=True)
        .order_by('sort_order', 'code')
        .values('code', 'label', 'kind', 'endpoint', 'value_field', 'label_field')
    )
    for entry in custom_entries:
        entry['is_builtin'] = False
    return builtin_entries + custom_entries


def option_source_values(source: str):
    normalized = (source or '').strip()
    if normalized in BUILTIN_OPTION_SOURCE_MAP:
        return _builtin_option_values(normalized)
    registry_entry = OptionSourceRegistryEntry.objects.filter(code=normalized, is_active=True).first()
    if registry_entry:
        return _builtin_option_values(registry_entry.code)
    return []


def resolve_named_masterdata(model, value: str):
    normalized = (value or '').strip()
    if not normalized:
        return None
    candidate = model.objects.filter(code=normalized).first() or model.objects.filter(name=normalized).first()
    if candidate:
        return candidate
    for row in model.objects.exclude(aliases=[]):
        aliases = [str(alias).strip() for alias in row.aliases or []]
        if normalized in aliases:
            return row
    return None


def _builtin_option_values(source: str):
    if source == 'masterdata.departments':
        return [
            {'value': item.code, 'label': item.name, 'meta': {'id': str(item.id), 'level': item.level}}
            for item in Department.objects.filter(is_active=True).order_by('sort_order', 'code')
        ]
    if source == 'system.users':
        return [
            {
                'value': item.username,
                'label': item.display_name or item.username,
                'meta': {'id': item.id, 'primary_department': str(item.primary_department_id) if item.primary_department_id else None},
            }
            for item in User.objects.order_by('username')
        ]

    model = _masterdata_model_for_source(source)
    if model is None:
        return []
    return [
        {'value': item.code, 'label': item.name, 'meta': {'id': str(item.id), 'legacy_name': item.legacy_name}}
        for item in model.objects.filter(is_active=True).order_by('sort_order', 'code')
    ]


def _masterdata_model_for_source(source: str):
    from .models import Category, CostCenter, GLAccount, ProductLine, Project, ProjectCategory, Region, Vendor

    mapping = {
        'masterdata.categories': Category,
        'masterdata.project_categories': ProjectCategory,
        'masterdata.product_lines': ProductLine,
        'masterdata.projects': Project,
        'masterdata.vendors': Vendor,
        'masterdata.regions': Region,
        'masterdata.cost_centers': CostCenter,
        'masterdata.gl_accounts': GLAccount,
    }
    return mapping.get(source)

import hashlib
import json
import uuid
from copy import deepcopy
from dataclasses import dataclass

from budget_templates.access import (
    can_user_edit_template_field,
    can_user_input_template_field,
    can_user_view_template_field,
    normalize_field_rules,
)
from budget_templates.models import TemplateField
from rest_framework.exceptions import ValidationError


DEMAND_DATA_TYPES = {'text', 'number', 'money', 'date', 'boolean', 'option', 'json'}
DEMAND_INPUT_TYPES = {
    TemplateField.InputType.TEXT,
    TemplateField.InputType.NUMBER,
    TemplateField.InputType.SELECT,
    TemplateField.InputType.MULTI_SELECT,
    TemplateField.InputType.DATE,
    TemplateField.InputType.USER,
    TemplateField.InputType.DEPARTMENT,
    TemplateField.InputType.PROJECT,
}
SELECT_INPUT_TYPES = {TemplateField.InputType.SELECT, TemplateField.InputType.MULTI_SELECT}
ENTITY_INPUT_TYPES = {
    TemplateField.InputType.USER,
    TemplateField.InputType.DEPARTMENT,
    TemplateField.InputType.PROJECT,
}
RESERVED_PUBLIC_KEYS = {
    'budget_no',
    'description',
    'reason',
    'unit_price',
    'total_quantity',
    'total_amount',
    'monthly_plans',
}

CORE_SCHEMA_FIELDS = [
    {
        'code': 'budget_no',
        'label': '预算编号',
        'data_type': 'text',
        'input_type': TemplateField.InputType.TEXT,
        'required': False,
        'order': 10,
        'width': 180,
    },
    {
        'code': 'description',
        'label': '需求描述',
        'data_type': 'text',
        'input_type': TemplateField.InputType.TEXT,
        'required': True,
        'order': 20,
        'width': 260,
    },
    {
        'code': 'reason',
        'label': '需求原因',
        'data_type': 'text',
        'input_type': TemplateField.InputType.TEXT,
        'required': False,
        'order': 30,
        'width': 240,
    },
    {
        'code': 'unit_price',
        'label': '单价',
        'data_type': 'money',
        'input_type': TemplateField.InputType.NUMBER,
        'required': False,
        'order': 40,
        'width': 140,
    },
    {
        'code': 'total_quantity',
        'label': '数量',
        'data_type': 'number',
        'input_type': TemplateField.InputType.NUMBER,
        'required': False,
        'order': 50,
        'width': 120,
    },
    {
        'code': 'total_amount',
        'label': '总金额',
        'data_type': 'money',
        'input_type': TemplateField.InputType.NUMBER,
        'required': True,
        'order': 60,
        'width': 160,
    },
]
CORE_SCHEMA_BY_CODE = {field['code']: field for field in CORE_SCHEMA_FIELDS}


@dataclass
class DemandFieldProxy:
    input_type: str
    visible_rules: dict
    editable_rules: dict


def normalize_demand_schema(schema):
    if schema in (None, ''):
        schema = []
    if not isinstance(schema, list):
        raise ValidationError({'schema': 'schema 必须为数组。'})

    normalized_fields = {}
    for index, raw_field in enumerate(schema, start=1):
        if not isinstance(raw_field, dict):
            raise ValidationError({'schema': f'第 {index} 个字段配置必须为对象。'})
        code = str(raw_field.get('code', '')).strip()
        if not code:
            raise ValidationError({'schema': f'第 {index} 个字段缺少 code。'})
        if code in normalized_fields:
            raise ValidationError({'schema': f'字段 code {code} 重复。'})

        core_defaults = CORE_SCHEMA_BY_CODE.get(code, {})
        label = str(raw_field.get('label', core_defaults.get('label', code))).strip() or code
        data_type = str(raw_field.get('data_type', core_defaults.get('data_type', 'text'))).strip()
        input_type = str(raw_field.get('input_type', core_defaults.get('input_type', TemplateField.InputType.TEXT))).strip()
        if data_type not in DEMAND_DATA_TYPES:
            raise ValidationError({'schema': f'字段 {code} 的 data_type 不支持。'})
        if input_type not in DEMAND_INPUT_TYPES:
            raise ValidationError({'schema': f'字段 {code} 的 input_type 不支持。'})

        try:
            width = int(raw_field.get('width', core_defaults.get('width', 160)))
        except (TypeError, ValueError):
            raise ValidationError({'schema': f'字段 {code} 的 width 必须为数字。'})
        if width <= 0:
            raise ValidationError({'schema': f'字段 {code} 的 width 必须大于 0。'})

        try:
            order = int(raw_field.get('order', core_defaults.get('order', index * 10)))
        except (TypeError, ValueError):
            raise ValidationError({'schema': f'字段 {code} 的 order 必须为数字。'})

        option_source = str(raw_field.get('option_source', core_defaults.get('option_source', '')) or '').strip()
        if input_type in SELECT_INPUT_TYPES and not option_source:
            raise ValidationError({'schema': f'字段 {code} 为下拉类型时必须配置 option_source。'})
        if input_type in ENTITY_INPUT_TYPES and data_type != 'option':
            raise ValidationError({'schema': f'字段 {code} 为选择类输入时 data_type 必须为 option。'})
        if input_type not in SELECT_INPUT_TYPES:
            option_source = ''

        import_aliases = raw_field.get('import_aliases', core_defaults.get('import_aliases', [])) or []
        if not isinstance(import_aliases, list):
            raise ValidationError({'schema': f'字段 {code} 的 import_aliases 必须为数组。'})
        normalized_aliases = []
        for alias in import_aliases:
            alias_text = str(alias).strip()
            if alias_text and alias_text not in normalized_aliases:
                normalized_aliases.append(alias_text)

        visible_rules = normalize_field_rules(raw_field.get('visible_rules', core_defaults.get('visible_rules', {})), field_name='visible_rules')
        editable_rules = normalize_field_rules(raw_field.get('editable_rules', core_defaults.get('editable_rules', {})), field_name='editable_rules')

        normalized_fields[code] = {
            'code': code,
            'label': label,
            'data_type': data_type,
            'input_type': input_type,
            'required': bool(raw_field.get('required', core_defaults.get('required', False))),
            'order': order,
            'width': width,
            'frozen': bool(raw_field.get('frozen', core_defaults.get('frozen', False))),
            'option_source': option_source,
            'visible_rules': visible_rules,
            'editable_rules': editable_rules,
            'approval_included': bool(raw_field.get('approval_included', core_defaults.get('approval_included', True))),
            'dashboard_enabled': bool(raw_field.get('dashboard_enabled', core_defaults.get('dashboard_enabled', False))),
            'import_aliases': normalized_aliases,
        }

    for core_field in CORE_SCHEMA_FIELDS:
        if core_field['code'] not in normalized_fields:
            normalized_fields[core_field['code']] = {
                **core_field,
                'frozen': False,
                'option_source': '',
                'visible_rules': {},
                'editable_rules': {},
                'approval_included': True,
                'dashboard_enabled': False,
                'import_aliases': [],
            }

    return sorted(normalized_fields.values(), key=lambda item: (item['order'], item['code']))


def serialize_demand_schema(schema, *, user=None):
    serialized = []
    for field in normalize_demand_schema(schema):
        proxy = _field_proxy(field)
        if user and not can_user_view_template_field(user, proxy):
            continue
        serialized.append(
            {
                **field,
                'user_permissions': {
                    'visible': can_user_view_template_field(user, proxy) if user else True,
                    'editable': can_user_edit_template_field(user, proxy) if user else proxy.input_type != TemplateField.InputType.FORMULA,
                },
            }
        )
    return serialized


def normalize_demand_payload(payload, schema, *, user=None, existing_payload=None, enforce_all_required=False):
    if payload in (None, ''):
        payload = []
    if not isinstance(payload, list):
        raise ValidationError({'payload': 'payload 必须为数组。'})

    schema_fields = normalize_demand_schema(schema)
    field_map = {field['code']: field for field in schema_fields}
    normalized_rows = []
    existing_by_row_id = _payload_row_map(existing_payload or [])

    for row_index, raw_row in enumerate(payload, start=1):
        if not isinstance(raw_row, dict):
            raise ValidationError({'payload': f'第 {row_index} 行必须为对象。'})
        row_id = str(raw_row.get('_row_id') or uuid.uuid4())
        base_row = existing_by_row_id.get(row_id, {})
        normalized_row = {'_row_id': row_id}

        if existing_payload is not None:
            normalized_row.update({key: deepcopy(value) for key, value in base_row.items() if key != '_row_id'})

        for key, value in raw_row.items():
            if key == '_row_id':
                continue
            field = field_map.get(key)
            if field:
                proxy = _field_proxy(field)
                if existing_payload is not None and user and not can_user_edit_template_field(user, proxy):
                    continue
                normalized_row[key] = _normalize_field_value(field, value, row_index=row_index)
                continue
            normalized_row[key] = deepcopy(value)

        if existing_payload is not None and user:
            for code, field in field_map.items():
                proxy = _field_proxy(field)
                if not can_user_edit_template_field(user, proxy) and code in base_row:
                    normalized_row[code] = deepcopy(base_row[code])

        _validate_required_fields(normalized_row, schema_fields, user=user, row_index=row_index, enforce_all_required=enforce_all_required)
        normalized_rows.append(normalized_row)

    return normalized_rows


def filter_payload_for_user(payload, schema, *, user=None):
    schema_fields = normalize_demand_schema(schema)
    field_map = {field['code']: field for field in schema_fields}
    filtered_rows = []
    for row_index, row in enumerate(payload or [], start=1):
        if not isinstance(row, dict):
            continue
        filtered_row = {'_row_id': str(row.get('_row_id') or f'row-{row_index}')}
        for key, value in row.items():
            if key == '_row_id':
                continue
            field = field_map.get(key)
            if field:
                proxy = _field_proxy(field)
                if user and not can_user_view_template_field(user, proxy):
                    continue
                filtered_row[key] = deepcopy(value)
                continue
            if key in RESERVED_PUBLIC_KEYS or user is None:
                filtered_row[key] = deepcopy(value)
        filtered_rows.append(filtered_row)
    return filtered_rows


def hash_demand_payload(payload):
    serialized = json.dumps(payload or [], ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def demand_sheet_sync_status(sheet):
    if sheet.generated_budget_book_id:
        current_hash = hash_demand_payload(sheet.payload or [])
        if not sheet.generated_payload_hash or sheet.generated_payload_hash != current_hash:
            return 'stale'
        return 'in_sync'
    if sheet.status == 'confirmed':
        return 'ready'
    return 'pending'


def demand_sheet_sync_status_label(sheet):
    labels = {
        'pending': '待填写/待确认',
        'ready': '待生成预算',
        'in_sync': '已与预算同步',
        'stale': '已改动待重同步',
    }
    return labels[demand_sheet_sync_status(sheet)]


def _field_proxy(field):
    return DemandFieldProxy(
        input_type=field.get('input_type', TemplateField.InputType.TEXT),
        visible_rules=field.get('visible_rules') or {},
        editable_rules=field.get('editable_rules') or {},
    )


def _normalize_field_value(field, value, *, row_index):
    data_type = field['data_type']
    input_type = field['input_type']
    code = field['code']

    if value is None:
        return None

    if input_type == TemplateField.InputType.MULTI_SELECT:
        if value in ('', []):
            return []
        if not isinstance(value, list):
            raise ValidationError({'payload': f'第 {row_index} 行字段 {code} 必须为数组。'})
        return [str(item).strip() for item in value if str(item).strip()]

    if data_type == 'boolean':
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {'true', '1', 'yes', 'y', 'on'}:
                return True
            if lowered in {'false', '0', 'no', 'n', 'off', ''}:
                return False
        raise ValidationError({'payload': f'第 {row_index} 行字段 {code} 必须为布尔值。'})

    if data_type in {'number', 'money'}:
        if value == '':
            return ''
        try:
            json.dumps(value)
        except TypeError:
            raise ValidationError({'payload': f'第 {row_index} 行字段 {code} 不是有效数字。'})
        if isinstance(value, (list, dict)):
            raise ValidationError({'payload': f'第 {row_index} 行字段 {code} 不是有效数字。'})
        try:
            float(str(value))
        except (TypeError, ValueError):
            raise ValidationError({'payload': f'第 {row_index} 行字段 {code} 不是有效数字。'})
        return str(value).strip()

    if data_type == 'json':
        if value in ('', None):
            return {}
        if not isinstance(value, (dict, list)):
            raise ValidationError({'payload': f'第 {row_index} 行字段 {code} 必须为对象或数组。'})
        return deepcopy(value)

    if data_type == 'date':
        return str(value).strip()

    if data_type == 'option' and input_type == TemplateField.InputType.SELECT:
        return str(value).strip()

    return str(value).strip()


def _validate_required_fields(row, schema_fields, *, user=None, row_index, enforce_all_required=False):
    for field in schema_fields:
        if not field['required']:
            continue
        proxy = _field_proxy(field)
        should_enforce = enforce_all_required or user is None or can_user_input_template_field(user, proxy)
        if not should_enforce:
            continue
        value = row.get(field['code'])
        if _is_empty_value(value):
            raise ValidationError({'payload': f'第 {row_index} 行缺少 {field["code"]}。'})


def _is_empty_value(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, dict):
        return len(value) == 0
    return False


def _payload_row_map(payload):
    mapping = {}
    for row_index, row in enumerate(payload or [], start=1):
        if not isinstance(row, dict):
            continue
        row_id = str(row.get('_row_id') or f'row-{row_index}')
        mapping[row_id] = row
    return mapping

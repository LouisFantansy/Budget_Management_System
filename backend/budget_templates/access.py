from rest_framework.exceptions import ValidationError

from accounts.access import is_global_budget_user
from .models import TemplateField


PRIMARY_SCOPE = 'primary'
SECONDARY_SCOPE = 'secondary'
ALLOWED_SCOPES = {PRIMARY_SCOPE, SECONDARY_SCOPE}


def normalize_field_rules(rules, *, field_name):
    rules = rules or {}
    if not isinstance(rules, dict):
        raise ValidationError({field_name: '字段权限规则必须为对象。'})

    if field_name == 'visible_rules':
        raw_scopes = rules.get('visible_to')
        if raw_scopes is None and rules.get('secondary_hidden'):
            raw_scopes = [PRIMARY_SCOPE]
        if raw_scopes is None:
            return {}
        return {'visible_to': _normalize_scope_list(raw_scopes, field_name=field_name, rule_key='visible_to')}

    if field_name == 'editable_rules':
        raw_scopes = rules.get('editable_by')
        if raw_scopes is None and rules.get('secondary_readonly'):
            raw_scopes = [PRIMARY_SCOPE]
        if raw_scopes is None:
            return {}
        return {'editable_by': _normalize_scope_list(raw_scopes, field_name=field_name, rule_key='editable_by')}

    raise ValidationError({field_name: '不支持的字段权限规则。'})


def template_fields_for_user(template, user=None, *, scope='visible'):
    fields = list(template.fields.all())
    if user is None:
        return fields
    if scope == 'all':
        return fields
    if scope == 'visible':
        return [field for field in fields if can_user_view_template_field(user, field)]
    if scope == 'input':
        return [field for field in fields if can_user_input_template_field(user, field)]
    raise ValueError(f'unsupported scope: {scope}')


def can_user_view_template_field(user, field):
    if user is None:
        return True
    visible_rules = normalize_field_rules(field.visible_rules, field_name='visible_rules')
    visible_to = visible_rules.get('visible_to')
    if not visible_to:
        return True
    return bool(_user_scopes(user) & set(visible_to))


def can_user_edit_template_field(user, field):
    if user is None:
        return field.input_type != TemplateField.InputType.FORMULA
    if field.input_type == TemplateField.InputType.FORMULA:
        return False
    editable_rules = normalize_field_rules(field.editable_rules, field_name='editable_rules')
    editable_by = editable_rules.get('editable_by')
    if not editable_by:
        return True
    return bool(_user_scopes(user) & set(editable_by))


def can_user_input_template_field(user, field):
    return can_user_view_template_field(user, field) and can_user_edit_template_field(user, field)


def filter_dynamic_data_for_user(template, dynamic_data, user=None):
    dynamic_data = dynamic_data or {}
    if user is None:
        return dynamic_data
    visible_codes = {
        field.code
        for field in template_fields_for_user(template, user, scope='visible')
    }
    return {
        code: value
        for code, value in dynamic_data.items()
        if code in visible_codes
    }


def _normalize_scope_list(values, *, field_name, rule_key):
    if not isinstance(values, (list, tuple, set)):
        raise ValidationError({field_name: f'{rule_key} 必须为数组。'})
    normalized = []
    for value in values:
        if value not in ALLOWED_SCOPES:
            raise ValidationError({field_name: f'{rule_key} 仅支持 primary / secondary。'})
        if value not in normalized:
            normalized.append(value)
    return normalized


def _user_scopes(user):
    if not user or not user.is_authenticated:
        return set()
    if is_global_budget_user(user):
        return {PRIMARY_SCOPE, SECONDARY_SCOPE}
    return {SECONDARY_SCOPE}

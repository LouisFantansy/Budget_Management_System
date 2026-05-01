from datetime import date
from decimal import Decimal, InvalidOperation

from rest_framework.exceptions import ValidationError

from budget_templates.models import TemplateField


def validate_dynamic_data(template, dynamic_data):
    errors = collect_dynamic_data_errors(template, dynamic_data)
    if errors:
        raise ValidationError({'dynamic_data': errors})


def collect_dynamic_data_errors(template, dynamic_data):
    errors = {}
    dynamic_data = dynamic_data or {}
    fields = template.fields.all()

    for field in fields:
        value = dynamic_data.get(field.code)
        if field.required and _is_empty(value):
            errors[field.code] = '该字段必填。'
            continue
        if _is_empty(value):
            continue
        if not _is_valid_type(field, value):
            errors[field.code] = f'字段类型必须为 {field.get_data_type_display()}。'

    return errors


def _is_empty(value):
    return value is None or value == '' or value == []


def _is_valid_type(field, value):
    if field.data_type in [TemplateField.DataType.TEXT, TemplateField.DataType.OPTION, TemplateField.DataType.JSON]:
        return True
    if field.data_type in [TemplateField.DataType.NUMBER, TemplateField.DataType.MONEY]:
        try:
            Decimal(str(value))
        except (InvalidOperation, ValueError):
            return False
        return True
    if field.data_type == TemplateField.DataType.BOOLEAN:
        return isinstance(value, bool)
    if field.data_type == TemplateField.DataType.DATE:
        if isinstance(value, date):
            return True
        if not isinstance(value, str):
            return False
        try:
            date.fromisoformat(value)
        except ValueError:
            return False
        return True
    return True

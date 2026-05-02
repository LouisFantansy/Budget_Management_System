import ast
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from rest_framework.exceptions import ValidationError

from budget_templates.models import TemplateField


def validate_dynamic_data(template, dynamic_data, formula_context=None):
    dynamic_data, formula_errors = resolve_dynamic_data(template, dynamic_data, formula_context=formula_context)
    errors = collect_dynamic_data_errors(template, dynamic_data)
    errors.update(formula_errors)
    if errors:
        raise ValidationError({'dynamic_data': errors})
    return dynamic_data


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


def validate_template_formula(template, field, formula):
    if not formula:
        return
    evaluator = FormulaEvaluator(template)
    try:
        evaluator.validate(formula, target_field=field)
    except FormulaValidationError as exc:
        raise ValidationError({'formula': str(exc)}) from exc


def apply_template_formulas(template, dynamic_data):
    evaluator = FormulaEvaluator(template)
    errors = {}
    computed = dict(dynamic_data or {})
    formula_fields = [
        field for field in template.fields.all()
        if field.input_type == TemplateField.InputType.FORMULA and field.formula
    ]
    for field in formula_fields:
        try:
            computed[field.code] = evaluator.evaluate(field.formula, computed, target_field=field)
        except FormulaValidationError as exc:
            errors[field.code] = str(exc)
    return computed, errors


def resolve_dynamic_data(template, dynamic_data, formula_context=None):
    context = dict(dynamic_data or {})
    if formula_context:
        context.update(formula_context)
    computed_context, errors = apply_template_formulas(template, context)
    field_codes = {field.code for field in template.fields.all()}
    resolved = {
        code: value
        for code, value in computed_context.items()
        if code in field_codes and value not in (None, '')
    }
    return resolved, errors


@dataclass
class FormulaValidationError(Exception):
    message: str

    def __str__(self):
        return self.message


class FormulaEvaluator:
    ALLOWED_FUNCTIONS = {'sum_month_qty', 'sum_month_amount'}
    ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
    ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)

    def __init__(self, template):
        self.template = template
        self.field_map = {field.code: field for field in template.fields.all()}

    def validate(self, formula, target_field=None):
        expression = self._parse(formula)
        self._validate_node(expression.body, target_field=target_field)

    def evaluate(self, formula, dynamic_data, target_field=None):
        expression = self._parse(formula)
        self._validate_node(expression.body, target_field=target_field)
        value = self._eval_node(expression.body, dynamic_data or {})
        return self._normalize_result(value, target_field)

    def _parse(self, formula):
        try:
            return ast.parse(formula, mode='eval')
        except SyntaxError as exc:
            raise FormulaValidationError('公式语法错误。') from exc

    def _validate_node(self, node, target_field=None):
        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, self.ALLOWED_BINOPS):
                raise FormulaValidationError('公式仅支持 + - * / 运算。')
            self._validate_node(node.left, target_field=target_field)
            self._validate_node(node.right, target_field=target_field)
            return
        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, self.ALLOWED_UNARYOPS):
                raise FormulaValidationError('公式存在不支持的一元运算。')
            self._validate_node(node.operand, target_field=target_field)
            return
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in self.ALLOWED_FUNCTIONS:
                raise FormulaValidationError('公式使用了不支持的函数。')
            if node.keywords:
                raise FormulaValidationError('公式函数不支持关键字参数。')
            for argument in node.args:
                self._validate_node(argument, target_field=target_field)
            return
        if isinstance(node, ast.Name):
            if target_field and node.id == target_field.code:
                raise FormulaValidationError('公式不能依赖自身字段。')
            if node.id in self.field_map and self.field_map[node.id].input_type == TemplateField.InputType.FORMULA:
                raise FormulaValidationError('当前仅支持公式依赖基础字段，暂不支持引用其他公式字段。')
            if node.id not in self.field_map and node.id not in {'unit_price', 'total_quantity', 'total_amount'}:
                raise FormulaValidationError(f'公式引用了不存在的字段: {node.id}')
            return
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float, str)):
                return
            raise FormulaValidationError('公式常量类型不受支持。')
        raise FormulaValidationError('公式存在不支持的表达式。')

    def _eval_node(self, node, dynamic_data):
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, dynamic_data)
            right = self._eval_node(node.right, dynamic_data)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == Decimal('0.00'):
                    raise FormulaValidationError('公式除数不能为 0。')
                return left / right
        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, dynamic_data)
            return operand if isinstance(node.op, ast.UAdd) else -operand
        if isinstance(node, ast.Call):
            function_name = node.func.id
            if function_name == 'sum_month_qty':
                return _sum_month_series(dynamic_data.get('monthly_quantities') or [])
            if function_name == 'sum_month_amount':
                return _sum_month_series(dynamic_data.get('monthly_amounts') or [])
        if isinstance(node, ast.Name):
            return _coerce_formula_value(dynamic_data.get(node.id))
        if isinstance(node, ast.Constant):
            return _coerce_formula_value(node.value)
        raise FormulaValidationError('公式计算失败。')

    def _normalize_result(self, value, field):
        if field is None:
            return str(value.quantize(Decimal('0.01')))
        if field.data_type == TemplateField.DataType.NUMBER:
            return str(value.quantize(Decimal('0.01')))
        if field.data_type == TemplateField.DataType.MONEY:
            return str(value.quantize(Decimal('0.01')))
        return str(value.quantize(Decimal('0.01')))


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


def _coerce_formula_value(value):
    if value in (None, '', []):
        return Decimal('0.00')
    if isinstance(value, bool):
        return Decimal('1.00') if value else Decimal('0.00')
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError) as exc:
        raise FormulaValidationError(f'公式依赖字段值不是合法数字: {value}') from exc


def _sum_month_series(values):
    total = Decimal('0.00')
    for value in values:
        total += _coerce_formula_value(value)
    return total.quantize(Decimal('0.01'))

from rest_framework import serializers

from accounts.access import can_edit_department_budget
from budget_templates.validation import validate_dynamic_data
from .models import BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion


class BudgetMonthlyPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetMonthlyPlan
        fields = '__all__'

    def validate_line(self, line):
        if line.version.status != BudgetVersion.Status.DRAFT:
            raise serializers.ValidationError('只能在 Draft 版本下维护月度计划。')
        request = self.context.get('request')
        if request and not can_edit_department_budget(request.user, line.version.book.department_id):
            raise serializers.ValidationError('没有权限维护该部门月度计划。')
        return line

    def update(self, instance, validated_data):
        if instance.line.version.status != BudgetVersion.Status.DRAFT:
            raise serializers.ValidationError({'line': '已送审或已审批版本不可修改月度计划。'})
        request = self.context.get('request')
        if request and not can_edit_department_budget(request.user, instance.line.version.book.department_id):
            raise serializers.ValidationError({'line': '没有权限维护该部门月度计划。'})
        return super().update(instance, validated_data)


class BudgetLineSerializer(serializers.ModelSerializer):
    monthly_plans = BudgetMonthlyPlanSerializer(many=True, read_only=True)

    class Meta:
        model = BudgetLine
        fields = '__all__'

    def validate_version(self, version):
        if version.status != BudgetVersion.Status.DRAFT:
            raise serializers.ValidationError('只能在 Draft 版本下维护预算条目。')
        request = self.context.get('request')
        if request and not can_edit_department_budget(request.user, version.book.department_id):
            raise serializers.ValidationError('没有权限维护该部门预算条目。')
        return version

    def validate(self, attrs):
        version = attrs.get('version') or getattr(self.instance, 'version', None)
        if version:
            dynamic_data = self._merged_dynamic_data(attrs)
            validate_dynamic_data(version.book.template, dynamic_data)
        return attrs

    def update(self, instance, validated_data):
        if instance.version.status != BudgetVersion.Status.DRAFT:
            raise serializers.ValidationError({'version': '已送审或已审批版本不可修改预算条目。'})
        request = self.context.get('request')
        if request and not can_edit_department_budget(request.user, instance.version.book.department_id):
            raise serializers.ValidationError({'version': '没有权限维护该部门预算条目。'})
        if 'dynamic_data' in validated_data:
            merged = dict(instance.dynamic_data or {})
            merged.update(validated_data['dynamic_data'] or {})
            validated_data['dynamic_data'] = merged
        return super().update(instance, validated_data)

    def _merged_dynamic_data(self, attrs):
        if self.instance is None:
            return attrs.get('dynamic_data') or {}
        if 'dynamic_data' not in attrs:
            return self.instance.dynamic_data or {}
        merged = dict(self.instance.dynamic_data or {})
        merged.update(attrs.get('dynamic_data') or {})
        return merged


class BudgetVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetVersion
        fields = '__all__'


class BudgetBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetBook
        fields = '__all__'

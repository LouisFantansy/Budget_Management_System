from rest_framework import serializers

from accounts.access import can_edit_department_budget, is_global_budget_user
from budget_templates.validation import validate_dynamic_data
from .models import AllocationUpload, BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion, ImportJob


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
        if request and not is_global_budget_user(request.user) and not line.editable_by_secondary:
            raise serializers.ValidationError('该预算条目已锁定，需回到来源模块维护。')
        return line

    def update(self, instance, validated_data):
        if instance.line.version.status != BudgetVersion.Status.DRAFT:
            raise serializers.ValidationError({'line': '已送审或已审批版本不可修改月度计划。'})
        request = self.context.get('request')
        if request and not can_edit_department_budget(request.user, instance.line.version.book.department_id):
            raise serializers.ValidationError({'line': '没有权限维护该部门月度计划。'})
        if request and not is_global_budget_user(request.user) and not instance.line.editable_by_secondary:
            raise serializers.ValidationError({'line': '该预算条目已锁定，需回到来源模块维护。'})
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
        if request and version.book.source_type == BudgetBook.SourceType.SPECIAL and not is_global_budget_user(request.user):
            raise serializers.ValidationError('专题生成预算需回到专题需求模块维护。')
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
        if request and not is_global_budget_user(request.user) and not instance.editable_by_secondary:
            raise serializers.ValidationError({'version': '该预算条目已锁定，需回到来源模块维护。'})
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


class BudgetLineBulkActionSerializer(serializers.Serializer):
    class Action(serializers.ChoiceField):
        pass

    action = serializers.ChoiceField(choices=['delete', 'duplicate', 'patch'])
    line_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    patch = serializers.JSONField(required=False)

    def validate(self, attrs):
        action = attrs['action']
        patch_data = attrs.get('patch')
        if action != 'patch':
            attrs['patch'] = {}
            return attrs

        if not isinstance(patch_data, dict) or not patch_data:
            raise serializers.ValidationError({'patch': '批量更新必须提供 patch 字段。'})

        allowed_fields = {
            'budget_no',
            'cost_center_code',
            'gl_amount_code',
            'category',
            'category_l1',
            'category_l2',
            'project',
            'project_category',
            'product_line',
            'description',
            'vendor',
            'reason',
            'region',
            'unit_price',
            'total_quantity',
            'total_amount',
            'dynamic_data',
            'local_comments',
        }
        invalid_fields = sorted(set(patch_data.keys()) - allowed_fields)
        if invalid_fields:
            raise serializers.ValidationError({'patch': f'不支持批量更新字段: {", ".join(invalid_fields)}'})
        if 'dynamic_data' in patch_data and not isinstance(patch_data['dynamic_data'], dict):
            raise serializers.ValidationError({'patch': 'dynamic_data 必须为对象。'})
        if 'local_comments' in patch_data and not isinstance(patch_data['local_comments'], dict):
            raise serializers.ValidationError({'patch': 'local_comments 必须为对象。'})
        return attrs


class ImportJobSerializer(serializers.ModelSerializer):
    requester_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ImportJob
        fields = '__all__'
        read_only_fields = [
            'requester',
            'status',
            'total_rows',
            'imported_rows',
            'error_rows',
            'summary',
            'errors',
        ]

    def get_requester_name(self, obj):
        if not obj.requester:
            return ''
        return obj.requester.display_name or obj.requester.username


class ImportJobCreateSerializer(serializers.Serializer):
    version = serializers.PrimaryKeyRelatedField(queryset=BudgetVersion.objects.select_related('book', 'book__department'))
    source_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    mode = serializers.ChoiceField(choices=ImportJob.Mode.choices, default=ImportJob.Mode.APPEND)
    raw_text = serializers.CharField()


class AllocationUploadSerializer(serializers.ModelSerializer):
    requester_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AllocationUpload
        fields = '__all__'
        read_only_fields = [
            'requester',
            'status',
            'total_rows',
            'imported_rows',
            'error_rows',
            'summary',
            'errors',
        ]

    def get_requester_name(self, obj):
        if not obj.requester:
            return ''
        return obj.requester.display_name or obj.requester.username


class AllocationUploadCreateSerializer(serializers.Serializer):
    cycle = serializers.PrimaryKeyRelatedField(queryset=BudgetBook.objects.none())
    source_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    raw_text = serializers.CharField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from budget_cycles.models import BudgetCycle

        self.fields['cycle'].queryset = BudgetCycle.objects.all()

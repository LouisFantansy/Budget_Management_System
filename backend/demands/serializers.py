from rest_framework import serializers

from accounts.access import accessible_department_ids, can_edit_department_budget, is_global_budget_user
from orgs.models import Department

from .models import DemandSheet, DemandTemplate


class DemandTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemandTemplate
        fields = '__all__'

    def validate_target_department(self, value):
        if value and value.level not in [Department.Level.PRIMARY, Department.Level.SS_PUBLIC]:
            raise serializers.ValidationError('模板归属部门仅支持一级部门 SS 或 SS public。')
        return value

    def validate(self, attrs):
        target_mode = attrs.get('target_mode') or getattr(self.instance, 'target_mode', DemandTemplate.TargetMode.SECONDARY)
        target_department = attrs.get('target_department', getattr(self.instance, 'target_department', None))
        if target_mode == DemandTemplate.TargetMode.SS_PUBLIC and target_department and target_department.level != Department.Level.SS_PUBLIC:
            raise serializers.ValidationError({'target_department': 'SS public 模式下必须选择 SS public 部门。'})
        return attrs


class DemandSheetSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    generated_budget_book_status = serializers.CharField(source='generated_budget_book.status', read_only=True)

    class Meta:
        model = DemandSheet
        fields = '__all__'
        read_only_fields = [
            'requested_by',
            'generated_budget_book',
            'generated_budget_version',
            'generated_line_count',
        ]

    def validate_template(self, value):
        if value.status != DemandTemplate.Status.ACTIVE:
            raise serializers.ValidationError('只能基于启用状态的专题模板创建需求表。')
        return value

    def validate_target_department(self, value):
        if value.level not in [Department.Level.SECONDARY, Department.Level.SS_PUBLIC]:
            raise serializers.ValidationError('专题需求表仅支持二级部门或 SS public。')
        return value

    def validate_payload(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('payload 必须为数组。')
        for index, row in enumerate(value, start=1):
            if not isinstance(row, dict):
                raise serializers.ValidationError(f'第 {index} 行必须为对象。')
            if not row.get('description'):
                raise serializers.ValidationError(f'第 {index} 行缺少 description。')
            if 'total_amount' not in row:
                raise serializers.ValidationError(f'第 {index} 行缺少 total_amount。')
        return value

    def validate(self, attrs):
        template = attrs.get('template') or getattr(self.instance, 'template', None)
        target_department = attrs.get('target_department') or getattr(self.instance, 'target_department', None)
        if template and target_department:
            request = self.context.get('request')
            if template.target_mode == DemandTemplate.TargetMode.SS_PUBLIC:
                if target_department.level != Department.Level.SS_PUBLIC:
                    raise serializers.ValidationError({'target_department': 'SS public 专题只能挂到 SS public。'})
                if request and not is_global_budget_user(request.user):
                    raise serializers.ValidationError({'target_department': 'SS public 专题仅允许一级预算管理员维护。'})
            else:
                if target_department.level != Department.Level.SECONDARY:
                    raise serializers.ValidationError({'target_department': '二级专题只能挂到二级部门。'})
            if request and not is_global_budget_user(request.user):
                department_ids = {str(item) for item in accessible_department_ids(request.user)}
                if str(target_department.id) not in department_ids:
                    raise serializers.ValidationError({'target_department': '没有权限填报该部门专题需求。'})
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            validated_data['requested_by'] = request.user
        return super().create(validated_data)


class DemandGenerateSerializer(serializers.Serializer):
    force_rebuild = serializers.BooleanField(default=True)
    confirm = serializers.BooleanField(default=True)

    def validate(self, attrs):
        if not attrs.get('confirm'):
            raise serializers.ValidationError({'confirm': '生成预算前必须确认专题需求表。'})
        return attrs

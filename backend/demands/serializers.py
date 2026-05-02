from rest_framework import serializers

from accounts.access import accessible_department_ids, can_edit_department_budget, is_global_budget_user
from orgs.models import Department

from .models import DemandSheet, DemandTemplate
from .schema import (
    demand_sheet_sync_status,
    demand_sheet_sync_status_label,
    filter_payload_for_user,
    normalize_demand_payload,
    normalize_demand_schema,
    serialize_demand_schema,
)


class DemandTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemandTemplate
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = getattr(self.context.get('request'), 'user', None)
        data['schema'] = serialize_demand_schema(instance.schema, user=user)
        data['default_payload'] = filter_payload_for_user(instance.default_payload, instance.schema, user=user)
        return data

    def validate_target_department(self, value):
        if value and value.level not in [Department.Level.PRIMARY, Department.Level.SS_PUBLIC]:
            raise serializers.ValidationError('模板归属部门仅支持一级部门 SS 或 SS public。')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        target_mode = attrs.get('target_mode') or getattr(self.instance, 'target_mode', DemandTemplate.TargetMode.SECONDARY)
        target_department = attrs.get('target_department', getattr(self.instance, 'target_department', None))
        if target_mode == DemandTemplate.TargetMode.SS_PUBLIC and target_department and target_department.level != Department.Level.SS_PUBLIC:
            raise serializers.ValidationError({'target_department': 'SS public 模式下必须选择 SS public 部门。'})
        schema = normalize_demand_schema(attrs.get('schema', getattr(self.instance, 'schema', [])))
        attrs['schema'] = schema
        default_payload = attrs.get('default_payload', getattr(self.instance, 'default_payload', []))
        attrs['default_payload'] = normalize_demand_payload(default_payload, schema, enforce_all_required=False)
        return attrs


class DemandSheetSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    target_department_name = serializers.CharField(source='target_department.name', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.username', read_only=True)
    submitted_by_name = serializers.CharField(source='submitted_by.username', read_only=True)
    confirmed_by_name = serializers.CharField(source='confirmed_by.username', read_only=True)
    generated_by_name = serializers.CharField(source='generated_by.username', read_only=True)
    generated_budget_book_status = serializers.CharField(source='generated_budget_book.status', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    sync_status = serializers.SerializerMethodField()
    sync_status_label = serializers.SerializerMethodField()
    workflow_actions = serializers.SerializerMethodField()

    class Meta:
        model = DemandSheet
        fields = '__all__'
        read_only_fields = [
            'requested_by',
            'status',
            'schema_snapshot',
            'submitted_by',
            'submitted_at',
            'confirmed_by',
            'confirmed_at',
            'generated_budget_book',
            'generated_budget_version',
            'generated_line_count',
            'generated_by',
            'generated_at',
            'generated_payload_hash',
            'latest_comment',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = getattr(self.context.get('request'), 'user', None)
        schema = instance.schema_snapshot or instance.template.schema
        data['schema_snapshot'] = serialize_demand_schema(schema, user=user)
        data['payload'] = filter_payload_for_user(instance.payload, schema, user=user)
        return data

    def get_sync_status(self, obj):
        return demand_sheet_sync_status(obj)

    def get_sync_status_label(self, obj):
        return demand_sheet_sync_status_label(obj)

    def get_workflow_actions(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        can_manage_sheet = bool(
            user
            and user.is_authenticated
            and (is_global_budget_user(user) or can_edit_department_budget(user, obj.target_department_id))
        )
        can_edit_payload = can_manage_sheet and obj.status == DemandSheet.Status.DRAFT
        return {
            'can_edit_payload': can_edit_payload,
            'can_submit': can_edit_payload,
            'can_confirm': bool(user and user.is_authenticated and is_global_budget_user(user) and obj.status in {DemandSheet.Status.DRAFT, DemandSheet.Status.SUBMITTED}),
            'can_reopen': can_manage_sheet and obj.status in {DemandSheet.Status.SUBMITTED, DemandSheet.Status.CONFIRMED, DemandSheet.Status.GENERATED},
            'can_generate': bool(user and user.is_authenticated and is_global_budget_user(user) and obj.status in {DemandSheet.Status.CONFIRMED, DemandSheet.Status.GENERATED}),
        }

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
        attrs = super().validate(attrs)
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
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        sheet_schema = attrs.get('schema_snapshot')
        if not sheet_schema:
            if self.instance:
                if 'template' in attrs:
                    sheet_schema = normalize_demand_schema(template.schema)
                    attrs['schema_snapshot'] = sheet_schema
                else:
                    sheet_schema = self.instance.schema_snapshot or normalize_demand_schema(template.schema)
            elif template:
                sheet_schema = normalize_demand_schema(template.schema)
                attrs['schema_snapshot'] = sheet_schema

        payload_changed = 'payload' in attrs
        structure_changed = any(key in attrs for key in ['template', 'target_department'])
        if self.instance and (payload_changed or structure_changed) and self.instance.status != DemandSheet.Status.DRAFT:
            raise serializers.ValidationError({'status': '当前专题需求已提交或已同步预算，请先重新打开任务后再修改内容。'})

        if sheet_schema is not None:
            existing_payload = self.instance.payload if self.instance else None
            if payload_changed:
                attrs['payload'] = normalize_demand_payload(
                    attrs['payload'],
                    sheet_schema,
                    user=user,
                    existing_payload=existing_payload,
                    enforce_all_required=False,
                )
            elif not self.instance:
                payload = attrs.get('payload')
                if payload in (None, [], ''):
                    payload = template.default_payload if template else []
                attrs['payload'] = normalize_demand_payload(payload, sheet_schema, user=user, enforce_all_required=False)
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            validated_data['requested_by'] = request.user
        return super().create(validated_data)


class DemandGenerateSerializer(serializers.Serializer):
    force_rebuild = serializers.BooleanField(default=True)
    confirm = serializers.BooleanField(default=False)

    def validate(self, attrs):
        return attrs


class DemandWorkflowCommentSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, max_length=1000)

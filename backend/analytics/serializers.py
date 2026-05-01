from rest_framework import serializers

from accounts.access import accessible_department_ids, is_global_budget_user
from orgs.models import Department
from .models import DashboardConfig


class DashboardConfigSerializer(serializers.ModelSerializer):
    owner_name = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = DashboardConfig
        fields = '__all__'
        read_only_fields = ['owner']

    def get_owner_name(self, obj):
        return obj.owner.display_name or obj.owner.username

    def validate(self, attrs):
        request = self.context['request']
        user = request.user
        scope = attrs.get('scope', getattr(self.instance, 'scope', DashboardConfig.Scope.PERSONAL))
        department = attrs.get('department', getattr(self.instance, 'department', None))
        version_context = attrs.get('version_context', getattr(self.instance, 'version_context', 'latest_approved'))
        config = dict(attrs.get('config', getattr(self.instance, 'config', {})) or {})
        accessible_ids = {str(item_id) for item_id in accessible_department_ids(user)}

        if version_context not in {'latest_approved', 'current_draft'}:
            raise serializers.ValidationError({'version_context': '不支持的看板口径。'})

        if scope == DashboardConfig.Scope.GLOBAL and not is_global_budget_user(user):
            raise serializers.ValidationError({'scope': '只有一级预算角色可以维护全局看板。'})

        if scope == DashboardConfig.Scope.DEPARTMENT:
            if not department:
                raise serializers.ValidationError({'department': '部门共享看板必须选择部门。'})
            if not is_global_budget_user(user) and str(department.id) not in accessible_ids:
                raise serializers.ValidationError({'department': '只能共享到当前有权限的部门。'})
        else:
            attrs['department'] = None

        focus_department_id = config.get('focus_department_id')
        if focus_department_id in ('', None):
            config['focus_department_id'] = None
        else:
            try:
                focus_department = Department.objects.get(id=focus_department_id)
            except Department.DoesNotExist as error:
                raise serializers.ValidationError({'config': '聚焦部门不存在。'}) from error

            if not is_global_budget_user(user) and str(focus_department.id) not in accessible_ids:
                raise serializers.ValidationError({'config': '只能保存当前有权限的部门筛选。'})
            config['focus_department_id'] = str(focus_department.id)

        attrs['config'] = config
        return attrs

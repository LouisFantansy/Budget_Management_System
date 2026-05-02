from django.db.models import Q
from rest_framework import decorators, response, viewsets
from rest_framework.exceptions import ValidationError

from accounts.access import accessible_department_ids, is_global_budget_user
from .models import DashboardConfig
from .serializers import DashboardConfigSerializer
from .services import budget_drilldown, budget_overview as build_budget_overview


class DashboardConfigViewSet(viewsets.ModelViewSet):
    queryset = DashboardConfig.objects.select_related('owner', 'department').all()
    serializer_class = DashboardConfigSerializer
    filterset_fields = ['owner', 'scope', 'department', 'version_context', 'is_default']
    search_fields = ['name']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not user or not user.is_authenticated:
            return queryset.none()

        if is_global_budget_user(user):
            return queryset.filter(
                Q(owner=user, scope=DashboardConfig.Scope.PERSONAL)
                | Q(scope=DashboardConfig.Scope.DEPARTMENT)
                | Q(scope=DashboardConfig.Scope.GLOBAL)
            ).distinct()

        personal = queryset.filter(owner=user, scope=DashboardConfig.Scope.PERSONAL)
        department_ids = accessible_department_ids(user)
        department_shared = queryset.filter(scope=DashboardConfig.Scope.DEPARTMENT, department_id__in=department_ids)
        return (personal | department_shared).distinct()

    def perform_create(self, serializer):
        config = serializer.save(owner=self.request.user)
        self._ensure_single_default(config)

    def perform_update(self, serializer):
        self._assert_manage_permission(serializer.instance)
        config = serializer.save()
        self._ensure_single_default(config)

    def perform_destroy(self, instance):
        self._assert_manage_permission(instance)
        instance.delete()

    def _ensure_single_default(self, config):
        if not config.is_default:
            return
        queryset = DashboardConfig.objects.exclude(id=config.id).filter(scope=config.scope)
        if config.scope == DashboardConfig.Scope.PERSONAL:
            queryset = queryset.filter(owner=config.owner)
        elif config.scope == DashboardConfig.Scope.DEPARTMENT:
            queryset = queryset.filter(department=config.department)
        queryset.update(is_default=False)

    def _assert_manage_permission(self, config):
        user = self.request.user
        if config.owner_id == user.id or is_global_budget_user(user):
            return
        raise ValidationError({'permission': '只能维护自己创建的看板配置。'})

    @decorators.action(detail=False, methods=['get'], url_path='budget-overview')
    def budget_overview(self, request):
        version_context = request.query_params.get('version_context', 'latest_approved')
        department_ids = None if is_global_budget_user(request.user) else accessible_department_ids(request.user)
        focus_department_id = request.query_params.get('focus_department_id')
        expense_type = self._validated_expense_type(request.query_params.get('expense_type') or None)
        if focus_department_id:
            if department_ids is not None and focus_department_id not in {str(item_id) for item_id in department_ids}:
                raise ValidationError({'focus_department_id': '没有权限查看该部门。'})
            department_ids = [focus_department_id]
        return response.Response(
            build_budget_overview(
                version_context=version_context,
                department_ids=department_ids,
                expense_type=expense_type,
            )
        )

    @decorators.action(detail=False, methods=['get'], url_path='budget-drilldown')
    def budget_drilldown(self, request):
        version_context = request.query_params.get('version_context', 'latest_approved')
        dimension = request.query_params.get('dimension', 'department')
        value = request.query_params.get('value', '')
        expense_type = self._validated_expense_type(request.query_params.get('expense_type') or None)
        department_ids = None if is_global_budget_user(request.user) else accessible_department_ids(request.user)
        focus_department_id = request.query_params.get('focus_department_id')
        if focus_department_id:
            if department_ids is not None and focus_department_id not in {str(item_id) for item_id in department_ids}:
                raise ValidationError({'focus_department_id': '没有权限查看该部门。'})
            department_ids = [focus_department_id]
        try:
            payload = budget_drilldown(
                version_context=version_context,
                department_ids=department_ids,
                dimension=dimension,
                value=value,
                expense_type=expense_type,
            )
        except ValueError as error:
            raise ValidationError({'dimension': str(error)}) from error
        return response.Response(payload)

    @decorators.action(detail=True, methods=['get'], url_path='apply')
    def apply(self, request, pk=None):
        dashboard_config = self.get_object()
        department_ids = None if is_global_budget_user(request.user) else accessible_department_ids(request.user)
        focus_department_id = (dashboard_config.config or {}).get('focus_department_id')
        expense_type = (dashboard_config.config or {}).get('expense_type') or None
        if focus_department_id:
            if department_ids is not None and focus_department_id not in {str(item_id) for item_id in department_ids}:
                raise ValidationError({'focus_department_id': '没有权限查看该部门。'})
            department_ids = [focus_department_id]
        overview = build_budget_overview(
            version_context=dashboard_config.version_context,
            department_ids=department_ids,
            expense_type=expense_type,
        )
        return response.Response(
            {
                'config': DashboardConfigSerializer(dashboard_config, context={'request': request}).data,
                'overview': overview,
            }
        )

    def _validated_expense_type(self, expense_type):
        if expense_type in ('', None):
            return None
        if expense_type not in {'opex', 'capex'}:
            raise ValidationError({'expense_type': '不支持的费用类型。'})
        return expense_type

# Create your views here.

from django.http import HttpResponse
from rest_framework import decorators, response, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError

from accounts.access import accessible_department_ids, is_global_budget_user
from budgets.allocations import export_group_allocation_template, import_group_allocations
from budgets.serializers import BudgetVersionSerializer
from budgets.services import pull_primary_consolidated_book
from .models import BudgetCycle, BudgetTask
from .serializers import BudgetCycleSerializer, BudgetTaskSerializer
from .services import distribute_cycle_tasks


class BudgetCycleViewSet(viewsets.ModelViewSet):
    queryset = BudgetCycle.objects.all()
    serializer_class = BudgetCycleSerializer
    filterset_fields = ['year', 'status']
    search_fields = ['name']

    def perform_create(self, serializer):
        self._ensure_global_permission()
        serializer.save()

    def perform_update(self, serializer):
        self._ensure_global_permission()
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_global_permission()
        super().perform_destroy(instance)

    @decorators.action(detail=True, methods=['post'], url_path='pull-primary-consolidated')
    def pull_primary_consolidated(self, request, pk=None):
        if not is_global_budget_user(request.user):
            raise ValidationError({'permission': '只有一级预算角色可以拉取一级总表。'})
        expense_type = request.data.get('expense_type')
        if expense_type not in ['opex', 'capex']:
            raise ValidationError({'expense_type': 'expense_type 仅支持 opex 或 capex。'})
        draft = pull_primary_consolidated_book(self.get_object(), expense_type=expense_type, requester=request.user)
        return response.Response(BudgetVersionSerializer(draft).data, status=201)

    @decorators.action(detail=True, methods=['get'], url_path='group-allocation-template')
    def group_allocation_template(self, request, pk=None):
        if not is_global_budget_user(request.user):
            raise ValidationError({'permission': '只有一级预算角色可以下载集团分摊模板。'})
        csv_content = export_group_allocation_template()
        cycle = self.get_object()
        filename = f'group-allocation-{cycle.year}.csv'
        response_obj = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response_obj['Content-Disposition'] = f'attachment; filename=\"{filename}\"'
        return response_obj

    @decorators.action(detail=True, methods=['post'], url_path='import-group-allocation')
    def import_group_allocation(self, request, pk=None):
        if not is_global_budget_user(request.user):
            raise ValidationError({'permission': '只有一级预算角色可以导入集团分摊。'})
        raw_text = request.data.get('raw_text', '')
        upload = import_group_allocations(
            self.get_object(),
            request.user,
            source_name=request.data.get('source_name', ''),
            raw_text=raw_text,
        )
        from budgets.serializers import AllocationUploadSerializer

        serializer = AllocationUploadSerializer(upload)
        return response.Response(serializer.data, status=201)

    @decorators.action(detail=True, methods=['post'], url_path='distribute-tasks')
    def distribute_tasks(self, request, pk=None):
        self._ensure_global_permission()
        result = distribute_cycle_tasks(
            self.get_object(),
            requester=request.user,
            due_at=request.data.get('due_at'),
        )
        return response.Response(result, status=201)

    def _ensure_global_permission(self):
        if is_global_budget_user(self.request.user):
            return
        raise PermissionDenied('只有一级预算角色可以维护预算周期。')


class BudgetTaskViewSet(viewsets.ModelViewSet):
    queryset = BudgetTask.objects.select_related('cycle', 'department', 'owner').all()
    serializer_class = BudgetTaskSerializer
    filterset_fields = ['cycle', 'department', 'owner', 'status']

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_global_budget_user(self.request.user):
            return queryset
        department_ids = accessible_department_ids(self.request.user)
        return queryset.filter(department_id__in=department_ids)

    def perform_create(self, serializer):
        self._ensure_global_permission()
        serializer.save()

    def perform_update(self, serializer):
        self._ensure_global_permission()
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_global_permission()
        super().perform_destroy(instance)

    def _ensure_global_permission(self):
        if is_global_budget_user(self.request.user):
            return
        raise PermissionDenied('只有一级预算角色可以维护预算任务。')

# Create your views here.

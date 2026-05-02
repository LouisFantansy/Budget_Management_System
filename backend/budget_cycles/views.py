from django.http import HttpResponse
from rest_framework import decorators, response, viewsets
from rest_framework.exceptions import ValidationError

from accounts.access import is_global_budget_user
from budgets.allocations import export_group_allocation_template, import_group_allocations
from budgets.serializers import BudgetVersionSerializer
from budgets.services import pull_primary_consolidated_book
from .models import BudgetCycle, BudgetTask
from .serializers import BudgetCycleSerializer, BudgetTaskSerializer


class BudgetCycleViewSet(viewsets.ModelViewSet):
    queryset = BudgetCycle.objects.all()
    serializer_class = BudgetCycleSerializer
    filterset_fields = ['year', 'status']
    search_fields = ['name']

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


class BudgetTaskViewSet(viewsets.ModelViewSet):
    queryset = BudgetTask.objects.select_related('cycle', 'department', 'owner').all()
    serializer_class = BudgetTaskSerializer
    filterset_fields = ['cycle', 'department', 'owner', 'status']

# Create your views here.

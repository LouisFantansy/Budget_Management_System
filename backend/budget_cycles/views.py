from rest_framework import decorators, response, viewsets
from rest_framework.exceptions import ValidationError

from accounts.access import is_global_budget_user
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


class BudgetTaskViewSet(viewsets.ModelViewSet):
    queryset = BudgetTask.objects.select_related('cycle', 'department', 'owner').all()
    serializer_class = BudgetTaskSerializer
    filterset_fields = ['cycle', 'department', 'owner', 'status']

# Create your views here.

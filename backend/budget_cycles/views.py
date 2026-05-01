from rest_framework import viewsets

from .models import BudgetCycle, BudgetTask
from .serializers import BudgetCycleSerializer, BudgetTaskSerializer


class BudgetCycleViewSet(viewsets.ModelViewSet):
    queryset = BudgetCycle.objects.all()
    serializer_class = BudgetCycleSerializer
    filterset_fields = ['year', 'status']
    search_fields = ['name']


class BudgetTaskViewSet(viewsets.ModelViewSet):
    queryset = BudgetTask.objects.select_related('cycle', 'department', 'owner').all()
    serializer_class = BudgetTaskSerializer
    filterset_fields = ['cycle', 'department', 'owner', 'status']

# Create your views here.

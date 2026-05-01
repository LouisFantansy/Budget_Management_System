from rest_framework import viewsets

from .models import BudgetTemplate, TemplateField
from .serializers import BudgetTemplateSerializer, TemplateFieldSerializer


class BudgetTemplateViewSet(viewsets.ModelViewSet):
    queryset = BudgetTemplate.objects.prefetch_related('fields').select_related('cycle', 'copied_from').all()
    serializer_class = BudgetTemplateSerializer
    filterset_fields = ['cycle', 'expense_type', 'status', 'schema_version']
    search_fields = ['name']


class TemplateFieldViewSet(viewsets.ModelViewSet):
    queryset = TemplateField.objects.select_related('template').all()
    serializer_class = TemplateFieldSerializer
    filterset_fields = ['template', 'data_type', 'input_type', 'required', 'dashboard_enabled']
    search_fields = ['code', 'label']

# Create your views here.

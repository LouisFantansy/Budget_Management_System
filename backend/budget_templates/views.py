from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from budgets.models import BudgetLine

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

    def perform_destroy(self, instance):
        is_referenced = BudgetLine.objects.filter(
            version__book__template=instance.template,
            dynamic_data__has_key=instance.code,
        ).exists()
        if is_referenced:
            raise ValidationError({'code': '该字段已被预算行使用，不能删除。'})
        super().perform_destroy(instance)

# Create your views here.

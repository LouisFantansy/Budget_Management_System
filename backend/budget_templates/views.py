from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError

from accounts.access import can_manage_template_schema
from budgets.models import BudgetLine

from .access import can_user_view_template_field
from .models import BudgetTemplate, TemplateField
from .serializers import BudgetTemplateSerializer, TemplateFieldSerializer


class BudgetTemplateViewSet(viewsets.ModelViewSet):
    queryset = BudgetTemplate.objects.prefetch_related('fields').select_related('cycle', 'copied_from').all()
    serializer_class = BudgetTemplateSerializer
    filterset_fields = ['cycle', 'expense_type', 'status', 'schema_version']
    search_fields = ['name']

    def perform_create(self, serializer):
        self._ensure_template_schema_access()
        serializer.save()

    def perform_update(self, serializer):
        self._ensure_template_schema_access()
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_template_schema_access()
        super().perform_destroy(instance)

    def _ensure_template_schema_access(self):
        if can_manage_template_schema(self.request.user):
            return
        raise PermissionDenied('只有一级预算管理员可以维护预算模板。')


class TemplateFieldViewSet(viewsets.ModelViewSet):
    queryset = TemplateField.objects.select_related('template').all()
    serializer_class = TemplateFieldSerializer
    filterset_fields = ['template', 'data_type', 'input_type', 'required', 'dashboard_enabled']
    search_fields = ['code', 'label']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if can_manage_template_schema(user):
            return queryset
        visible_ids = [
            field.id for field in queryset
            if can_user_view_template_field(user, field)
        ]
        return queryset.filter(id__in=visible_ids)

    def perform_create(self, serializer):
        self._ensure_template_schema_access()
        serializer.save()

    def perform_update(self, serializer):
        self._ensure_template_schema_access()
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_template_schema_access()
        is_referenced = BudgetLine.objects.filter(
            version__book__template=instance.template,
            dynamic_data__has_key=instance.code,
        ).exists()
        if is_referenced:
            raise ValidationError({'code': '该字段已被预算行使用，不能删除。'})
        super().perform_destroy(instance)

    def _ensure_template_schema_access(self):
        if can_manage_template_schema(self.request.user):
            return
        raise PermissionDenied('只有一级预算管理员可以维护模板字段。')

# Create your views here.

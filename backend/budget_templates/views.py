from rest_framework import decorators, response, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError

from accounts.access import can_manage_template_schema
from budget_cycles.models import BudgetCycle
from budgets.models import BudgetLine

from .access import can_user_view_template_field
from .models import BudgetTemplate, TemplateField
from .serializers import BudgetTemplateSerializer, TemplateFieldSerializer
from .services import bootstrap_cycle_templates, create_template_revision


class BudgetTemplateViewSet(viewsets.ModelViewSet):
    queryset = BudgetTemplate.objects.prefetch_related('fields').select_related('cycle', 'copied_from').all()
    serializer_class = BudgetTemplateSerializer
    filterset_fields = ['cycle', 'expense_type', 'status', 'schema_version']
    search_fields = ['name']

    def perform_create(self, serializer):
        self._ensure_template_schema_access()
        template = serializer.save()
        self._ensure_single_active_template(template)

    def perform_update(self, serializer):
        self._ensure_template_schema_access()
        template = serializer.save()
        self._ensure_single_active_template(template)

    def perform_destroy(self, instance):
        self._ensure_template_schema_access()
        super().perform_destroy(instance)

    @decorators.action(detail=True, methods=['post'], url_path='create-revision')
    def create_revision(self, request, pk=None):
        self._ensure_template_schema_access()
        template = self.get_object()
        revision = create_template_revision(template)
        serializer = self.get_serializer(revision)
        return response.Response(serializer.data, status=201)

    @decorators.action(detail=False, methods=['post'], url_path='bootstrap-from-previous')
    def bootstrap_from_previous(self, request):
        self._ensure_template_schema_access()
        cycle_id = request.data.get('cycle')
        if not cycle_id:
            raise ValidationError({'cycle': '必须指定目标预算周期。'})
        try:
            cycle = BudgetCycle.objects.get(id=cycle_id)
        except BudgetCycle.DoesNotExist as error:
            raise ValidationError({'cycle': '预算周期不存在。'}) from error
        try:
            previous_cycle, created = bootstrap_cycle_templates(cycle)
        except ValueError as error:
            raise ValidationError({'cycle': str(error)}) from error
        serializer = self.get_serializer(created, many=True)
        return response.Response(
            {
                'cycle': str(cycle.id),
                'previous_cycle': str(previous_cycle.id),
                'created_count': len(created),
                'results': serializer.data,
            },
            status=201,
        )

    def _ensure_template_schema_access(self):
        if can_manage_template_schema(self.request.user):
            return
        raise PermissionDenied('只有一级预算管理员可以维护预算模板。')

    def _ensure_single_active_template(self, template):
        if template.status != BudgetTemplate.Status.ACTIVE:
            return
        BudgetTemplate.objects.exclude(id=template.id).filter(
            cycle=template.cycle,
            expense_type=template.expense_type,
            status=BudgetTemplate.Status.ACTIVE,
        ).update(status=BudgetTemplate.Status.ARCHIVED)


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

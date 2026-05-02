from django.db.models import Q
from rest_framework import decorators, response, viewsets
from rest_framework.exceptions import ValidationError

from accounts.access import accessible_department_ids, can_edit_department_budget, is_global_budget_user
from budgets.serializers import BudgetVersionSerializer

from .models import DemandSheet, DemandTemplate
from .serializers import DemandGenerateSerializer, DemandSheetSerializer, DemandTemplateSerializer
from .services import generate_budget_lines_from_sheet


class DemandTemplateViewSet(viewsets.ModelViewSet):
    queryset = DemandTemplate.objects.select_related('cycle', 'target_department').all()
    serializer_class = DemandTemplateSerializer
    filterset_fields = ['cycle', 'status', 'target_mode', 'target_department']
    search_fields = ['name']

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_global_budget_user(self.request.user):
            return queryset
        return queryset.filter(status=DemandTemplate.Status.ACTIVE, target_mode=DemandTemplate.TargetMode.SECONDARY)

    def perform_create(self, serializer):
        if not is_global_budget_user(self.request.user):
            raise ValidationError({'permission': '只有一级预算角色可以创建专题模板。'})
        serializer.save()

    def perform_update(self, serializer):
        if not is_global_budget_user(self.request.user):
            raise ValidationError({'permission': '只有一级预算角色可以维护专题模板。'})
        serializer.save()

    def perform_destroy(self, instance):
        if not is_global_budget_user(self.request.user):
            raise ValidationError({'permission': '只有一级预算角色可以删除专题模板。'})
        super().perform_destroy(instance)


class DemandSheetViewSet(viewsets.ModelViewSet):
    queryset = DemandSheet.objects.select_related(
        'template',
        'template__cycle',
        'target_department',
        'requested_by',
        'generated_budget_book',
        'generated_budget_version',
    ).all()
    serializer_class = DemandSheetSerializer
    filterset_fields = ['template', 'template__cycle', 'target_department', 'status']
    search_fields = ['template__name', 'target_department__name', 'target_department__code']

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_global_budget_user(self.request.user):
            return queryset
        department_ids = accessible_department_ids(self.request.user)
        return queryset.filter(target_department_id__in=department_ids)

    def perform_create(self, serializer):
        target_department = serializer.validated_data['target_department']
        if not (is_global_budget_user(self.request.user) or can_edit_department_budget(self.request.user, target_department.id)):
            raise ValidationError({'permission': '没有权限创建该部门专题需求。'})
        serializer.save()

    def perform_update(self, serializer):
        target_department = serializer.validated_data.get('target_department', serializer.instance.target_department)
        if not (is_global_budget_user(self.request.user) or can_edit_department_budget(self.request.user, target_department.id)):
            raise ValidationError({'permission': '没有权限维护该部门专题需求。'})
        serializer.save()

    def perform_destroy(self, instance):
        if not (is_global_budget_user(self.request.user) or can_edit_department_budget(self.request.user, instance.target_department_id)):
            raise ValidationError({'permission': '没有权限删除该部门专题需求。'})
        super().perform_destroy(instance)

    @decorators.action(detail=True, methods=['post'], url_path='generate-budget-lines')
    def generate_budget_lines(self, request, pk=None):
        sheet = self.get_object()
        if not (is_global_budget_user(request.user) or can_edit_department_budget(request.user, sheet.target_department_id)):
            raise ValidationError({'permission': '没有权限生成该专题需求预算。'})
        serializer = DemandGenerateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        result = generate_budget_lines_from_sheet(
            sheet,
            requester=request.user,
            force_rebuild=serializer.validated_data['force_rebuild'],
        )
        return response.Response(
            {
                'sheet_id': str(sheet.id),
                'generated_line_count': result['generated_line_count'],
                'book_id': str(result['book'].id),
                'version': BudgetVersionSerializer(result['version']).data,
            },
            status=201,
        )

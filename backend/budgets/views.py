from django.http import HttpResponse
from django.db.models import Sum
from rest_framework import decorators, response, viewsets
from rest_framework.exceptions import ValidationError

from accounts.access import accessible_department_ids, can_edit_department_budget, is_global_budget_user
from .diff import compare_versions
from .import_export import (
    export_budget_version_csv,
    export_budget_version_import_sample_csv,
    export_budget_version_import_template_csv,
    import_budget_lines,
)
from .models import AllocationUpload, BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion
from .serializers import (
    AllocationUploadSerializer,
    BudgetBookSerializer,
    BudgetLineSerializer,
    BudgetLineBulkActionSerializer,
    BudgetMonthlyPlanSerializer,
    BudgetVersionSerializer,
    ImportJobCreateSerializer,
    ImportJobSerializer,
)
from .services import (
    bulk_operate_budget_lines,
    create_revision_draft,
    primary_consolidated_sync_status,
    submit_budget_version,
)


class BudgetBookViewSet(viewsets.ModelViewSet):
    queryset = BudgetBook.objects.select_related('cycle', 'department', 'template').all()
    serializer_class = BudgetBookSerializer
    filterset_fields = ['cycle', 'department', 'expense_type', 'source_type', 'status']

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_global_budget_user(self.request.user):
            return queryset
        department_ids = accessible_department_ids(self.request.user)
        return queryset.filter(department_id__in=department_ids)

    @decorators.action(detail=True, methods=['get'], url_path='dashboard-summary')
    def dashboard_summary(self, request, pk=None):
        book = self.get_object()
        version = book.latest_approved_version
        context = request.query_params.get('version_context', 'latest_approved')
        if context == 'current_draft' and book.current_draft_id:
            version = book.current_draft
        if not version:
            return response.Response({'version_context': context, 'line_count': 0, 'total_amount': '0.00'})
        total = version.lines.aggregate(total_amount=Sum('total_amount'))
        return response.Response(
            {
                'version_context': context,
                'version_id': str(version.id),
                'line_count': version.lines.count(),
                'total_amount': total['total_amount'] or 0,
            }
        )

    @decorators.action(detail=True, methods=['post'], url_path='create-revision')
    def create_revision(self, request, pk=None):
        book = self.get_object()
        if not can_edit_department_budget(request.user, book.department_id):
            raise ValidationError({'department': '没有权限创建该部门修订 Draft。'})
        draft = create_revision_draft(book, requester=request.user)
        serializer = BudgetVersionSerializer(draft)
        return response.Response(serializer.data, status=201)

    @decorators.action(detail=True, methods=['get'], url_path='sync-status')
    def sync_status(self, request, pk=None):
        book = self.get_object()
        return response.Response(primary_consolidated_sync_status(book))


class BudgetVersionViewSet(viewsets.ModelViewSet):
    queryset = BudgetVersion.objects.select_related('book', 'base_version', 'submitted_by', 'approved_by').all()
    serializer_class = BudgetVersionSerializer
    filterset_fields = ['book', 'status', 'version_no']

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_global_budget_user(self.request.user):
            return queryset
        department_ids = accessible_department_ids(self.request.user)
        return queryset.filter(book__department_id__in=department_ids)

    @decorators.action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        version = self.get_object()
        if not can_edit_department_budget(request.user, version.book.department_id):
            raise ValidationError({'department': '没有权限提交该部门预算。'})
        approval_request = submit_budget_version(
            version,
            request.user,
            approver_ids=request.data.get('approver_ids'),
            comment=request.data.get('comment', ''),
        )
        return response.Response(
            {
                'approval_request_id': str(approval_request.id),
                'status': approval_request.status,
                'target_id': str(approval_request.target_id),
            },
            status=201,
        )

    @decorators.action(detail=True, methods=['get'])
    def diff(self, request, pk=None):
        target_version = self.get_object()
        base_version_id = request.query_params.get('base_version')
        if base_version_id:
            base_version = BudgetVersion.objects.get(id=base_version_id)
        else:
            base_version = target_version.base_version
        if not base_version:
            raise ValidationError({'base_version': '请指定 base_version，或先为目标版本设置 base_version。'})
        try:
            payload = compare_versions(base_version, target_version)
        except ValueError as exc:
            raise ValidationError({'base_version': str(exc)}) from exc
        return response.Response(payload)

    @decorators.action(detail=True, methods=['get'], url_path='export-csv')
    def export_csv(self, request, pk=None):
        version = self.get_object()
        csv_content = export_budget_version_csv(version, user=request.user)
        filename = f'budget-version-{version.id}.csv'
        response_obj = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response_obj['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response_obj

    @decorators.action(detail=True, methods=['get'], url_path='import-template')
    def import_template(self, request, pk=None):
        version = self.get_object()
        csv_content = export_budget_version_import_template_csv(version, user=request.user)
        filename = f'budget-version-{version.id}-import-template.csv'
        response_obj = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response_obj['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response_obj

    @decorators.action(detail=True, methods=['get'], url_path='import-sample')
    def import_sample(self, request, pk=None):
        version = self.get_object()
        csv_content = export_budget_version_import_sample_csv(version, user=request.user)
        filename = f'budget-version-{version.id}-import-sample.csv'
        response_obj = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response_obj['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response_obj


class BudgetLineViewSet(viewsets.ModelViewSet):
    queryset = BudgetLine.objects.select_related('version', 'department', 'category', 'project').prefetch_related('monthly_plans').all()
    serializer_class = BudgetLineSerializer
    filterset_fields = ['version', 'department', 'category', 'project', 'editable_by_secondary']
    search_fields = ['description', 'budget_no']

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_global_budget_user(self.request.user):
            return queryset
        department_ids = accessible_department_ids(self.request.user)
        return queryset.filter(department_id__in=department_ids, version__book__department_id__in=department_ids)

    def perform_destroy(self, instance):
        if instance.version.status != BudgetVersion.Status.DRAFT:
            raise ValidationError({'version': '已送审或已审批版本不可删除预算条目。'})
        if not can_edit_department_budget(self.request.user, instance.version.book.department_id):
            raise ValidationError({'version': '没有权限删除该部门预算条目。'})
        if not is_global_budget_user(self.request.user) and not instance.editable_by_secondary:
            raise ValidationError({'version': '该预算条目已锁定，需回到来源模块维护。'})
        super().perform_destroy(instance)

    @decorators.action(detail=False, methods=['post'], url_path='bulk')
    def bulk(self, request):
        serializer = BudgetLineBulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        line_ids = serializer.validated_data['line_ids']
        lines = list(BudgetLine.objects.select_related('version', 'version__book').filter(id__in=line_ids))
        if not lines:
            raise ValidationError({'line_ids': '未找到可批量操作的预算条目。'})

        version_ids = {str(line.version_id) for line in lines}
        if len(version_ids) != 1:
            raise ValidationError({'line_ids': '批量操作只能作用于同一个 Draft 版本。'})

        version = lines[0].version
        if not can_edit_department_budget(request.user, version.book.department_id):
            raise ValidationError({'version': '没有权限批量维护该部门预算条目。'})

        result = bulk_operate_budget_lines(
            version,
            line_ids=line_ids,
            action=serializer.validated_data['action'],
            patch_data=serializer.validated_data.get('patch') or {},
            request=request,
        )
        return response.Response(result, status=200)


class BudgetMonthlyPlanViewSet(viewsets.ModelViewSet):
    queryset = BudgetMonthlyPlan.objects.select_related('line').all()
    serializer_class = BudgetMonthlyPlanSerializer
    filterset_fields = ['line', 'month']

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_global_budget_user(self.request.user):
            return queryset
        department_ids = accessible_department_ids(self.request.user)
        return queryset.filter(line__department_id__in=department_ids, line__version__book__department_id__in=department_ids)

    def perform_destroy(self, instance):
        if instance.line.version.status != BudgetVersion.Status.DRAFT:
            raise ValidationError({'line': '已送审或已审批版本不可删除月度计划。'})
        if not can_edit_department_budget(self.request.user, instance.line.version.book.department_id):
            raise ValidationError({'line': '没有权限删除该部门月度计划。'})
        if not is_global_budget_user(self.request.user) and not instance.line.editable_by_secondary:
            raise ValidationError({'line': '该预算条目已锁定，需回到来源模块维护。'})
        super().perform_destroy(instance)


class ImportJobViewSet(viewsets.ModelViewSet):
    queryset = BudgetVersion.objects.none()
    serializer_class = ImportJobSerializer
    filterset_fields = ['version', 'status', 'mode']
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        from .models import ImportJob

        queryset = ImportJob.objects.select_related('version', 'version__book', 'requester').all()
        if is_global_budget_user(self.request.user):
            return queryset
        department_ids = accessible_department_ids(self.request.user)
        return queryset.filter(version__book__department_id__in=department_ids)

    def get_serializer_class(self):
        if self.action == 'create':
            return ImportJobCreateSerializer
        return ImportJobSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        version = serializer.validated_data['version']
        if not can_edit_department_budget(request.user, version.book.department_id):
            raise ValidationError({'version': '没有权限导入该部门预算。'})
        job = import_budget_lines(
            version,
            request.user,
            source_name=serializer.validated_data.get('source_name', ''),
            raw_text=serializer.validated_data['raw_text'],
            mode=serializer.validated_data['mode'],
        )
        output = ImportJobSerializer(job, context=self.get_serializer_context())
        return response.Response(output.data, status=201)

    @decorators.action(detail=True, methods=['get'])
    def errors(self, request, pk=None):
        import_job = self.get_object()
        return response.Response(
            {
                'id': str(import_job.id),
                'status': import_job.status,
                'error_rows': import_job.error_rows,
                'errors': import_job.errors,
            }
        )


class AllocationUploadViewSet(viewsets.ModelViewSet):
    queryset = AllocationUpload.objects.select_related('cycle', 'requester').all()
    serializer_class = AllocationUploadSerializer
    filterset_fields = ['cycle', 'status']
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_global_budget_user(self.request.user):
            return queryset
        return queryset.none()

    def get_serializer_class(self):
        return AllocationUploadSerializer

# Create your views here.

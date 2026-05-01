from django.http import HttpResponse
from django.db.models import Sum
from rest_framework import decorators, response, viewsets
from rest_framework.exceptions import ValidationError

from accounts.access import accessible_department_ids, can_edit_department_budget, is_global_budget_user
from .diff import compare_versions
from .import_export import export_budget_version_csv, import_budget_lines
from .models import BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion
from .serializers import (
    BudgetBookSerializer,
    BudgetLineSerializer,
    BudgetMonthlyPlanSerializer,
    BudgetVersionSerializer,
    ImportJobCreateSerializer,
    ImportJobSerializer,
)
from .services import create_revision_draft, submit_budget_version


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
        csv_content = export_budget_version_csv(version)
        filename = f'budget-version-{version.id}.csv'
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
        super().perform_destroy(instance)


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

# Create your views here.

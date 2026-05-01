from rest_framework import decorators, response, viewsets

from accounts.access import accessible_department_ids, is_global_budget_user
from .models import DashboardConfig
from .serializers import DashboardConfigSerializer
from .services import budget_overview as build_budget_overview


class DashboardConfigViewSet(viewsets.ModelViewSet):
    queryset = DashboardConfig.objects.select_related('owner', 'department').all()
    serializer_class = DashboardConfigSerializer
    filterset_fields = ['owner', 'scope', 'department', 'version_context', 'is_default']
    search_fields = ['name']

    @decorators.action(detail=False, methods=['get'], url_path='budget-overview')
    def budget_overview(self, request):
        version_context = request.query_params.get('version_context', 'latest_approved')
        department_ids = None if is_global_budget_user(request.user) else accessible_department_ids(request.user)
        return response.Response(build_budget_overview(version_context=version_context, department_ids=department_ids))

# Create your views here.

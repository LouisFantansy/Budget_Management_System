from django.db.models import Q
from rest_framework import viewsets

from accounts.access import accessible_department_ids, is_global_budget_user

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related('actor', 'department', 'book', 'version').all()
    serializer_class = AuditLogSerializer
    filterset_fields = ['category', 'action', 'target_type', 'department', 'book', 'version']
    search_fields = ['action', 'target_type', 'target_label']

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_global_budget_user(self.request.user):
            return queryset
        department_ids = accessible_department_ids(self.request.user)
        return queryset.filter(Q(department_id__in=department_ids) | Q(department__isnull=True))

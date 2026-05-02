from django.db.models import Q
from rest_framework import decorators, response, viewsets

from accounts.access import accessible_department_ids, is_global_budget_user
from .models import Notification
from .serializers import NotificationMarkReadSerializer, NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Notification.objects.select_related('recipient', 'department').all()
    serializer_class = NotificationSerializer
    filterset_fields = ['category', 'status', 'department']
    search_fields = ['title', 'message']

    def get_queryset(self):
        queryset = super().get_queryset().filter(recipient=self.request.user)
        if is_global_budget_user(self.request.user):
            return queryset
        department_ids = accessible_department_ids(self.request.user)
        return queryset.filter(Q(department_id__in=department_ids) | Q(department__isnull=True))

    @decorators.action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        queryset = self.get_queryset()
        unread_count = queryset.filter(status=Notification.Status.UNREAD).count()
        return response.Response(
            {
                'total': queryset.count(),
                'unread_count': unread_count,
                'latest_unread_title': queryset.filter(status=Notification.Status.UNREAD).values_list('title', flat=True).first() or '',
            }
        )

    @decorators.action(detail=False, methods=['post'], url_path='mark-read')
    def mark_read(self, request):
        serializer = NotificationMarkReadSerializer(data=request.data, context={'queryset': self.get_queryset()})
        serializer.is_valid(raise_exception=True)
        count = serializer.save()
        return response.Response({'marked_count': count})

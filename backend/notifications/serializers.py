from django.utils import timezone
from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['recipient', 'category', 'title', 'message', 'target_type', 'target_id', 'department', 'extra', 'read_at']


class NotificationMarkReadSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=False)
    all = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if not attrs.get('all') and not attrs.get('ids'):
            raise serializers.ValidationError('请指定要标记的通知 ids，或传 all=true。')
        return attrs

    def save(self, **kwargs):
        queryset = self.context['queryset']
        if not self.validated_data.get('all'):
            queryset = queryset.filter(id__in=self.validated_data['ids'])
        now = timezone.now()
        count = queryset.filter(status=Notification.Status.UNREAD).update(status=Notification.Status.READ, read_at=now, updated_at=now)
        return count


from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.SerializerMethodField(read_only=True)
    book_id = serializers.SerializerMethodField(read_only=True)
    version_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AuditLog
        fields = '__all__'

    def get_actor_name(self, obj):
        if not obj.actor:
            return ''
        return obj.actor.display_name or obj.actor.username

    def get_department_name(self, obj):
        return obj.department.name if obj.department else ''

    def get_book_id(self, obj):
        return str(obj.book_id) if obj.book_id else None

    def get_version_id(self, obj):
        return str(obj.version_id) if obj.version_id else None

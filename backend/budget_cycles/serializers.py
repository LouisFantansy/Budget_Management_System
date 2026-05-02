from rest_framework import serializers

from .services import task_budget_context
from .models import BudgetCycle, BudgetTask


class BudgetCycleSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    task_count = serializers.IntegerField(source='tasks.count', read_only=True)

    class Meta:
        model = BudgetCycle
        fields = '__all__'


class BudgetTaskSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)
    owner_name = serializers.SerializerMethodField()
    cycle_name = serializers.CharField(source='cycle.name', read_only=True)

    class Meta:
        model = BudgetTask
        fields = '__all__'

    def to_representation(self, instance):
        payload = super().to_representation(instance)
        payload.update(task_budget_context(instance))
        return payload

    def get_owner_name(self, obj):
        if not obj.owner:
            return ''
        return obj.owner.display_name or obj.owner.username

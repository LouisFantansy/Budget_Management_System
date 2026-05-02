from rest_framework import serializers

from budgets.approval_flow import approval_stage_label
from budgets.diff import compare_versions
from budgets.models import BudgetVersion
from .models import ApprovalRequest, ApprovalStep


class ApprovalStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalStep
        fields = '__all__'


class ApprovalRequestSerializer(serializers.ModelSerializer):
    steps = ApprovalStepSerializer(many=True, read_only=True)
    diff_summary = serializers.SerializerMethodField()
    current_stage = serializers.SerializerMethodField()
    current_stage_label = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalRequest
        fields = '__all__'

    def get_diff_summary(self, obj):
        if obj.target_type != 'budget_version':
            return None
        try:
            target_version = BudgetVersion.objects.select_related('base_version').get(id=obj.target_id)
        except BudgetVersion.DoesNotExist:
            return None
        if not target_version.base_version_id:
            return None
        return compare_versions(target_version.base_version, target_version)['summary']

    def get_current_stage(self, obj):
        return (obj.dashboard_context or {}).get('approval_stage', '')

    def get_current_stage_label(self, obj):
        stage = self.get_current_stage(obj)
        return approval_stage_label(stage) if stage else ''

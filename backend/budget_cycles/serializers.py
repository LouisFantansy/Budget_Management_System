from rest_framework import serializers

from .models import BudgetCycle, BudgetTask


class BudgetCycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetCycle
        fields = '__all__'


class BudgetTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetTask
        fields = '__all__'

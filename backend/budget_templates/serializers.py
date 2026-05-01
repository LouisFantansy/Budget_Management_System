from rest_framework import serializers

from .models import BudgetTemplate, TemplateField


class TemplateFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateField
        fields = '__all__'


class BudgetTemplateSerializer(serializers.ModelSerializer):
    fields = TemplateFieldSerializer(many=True, read_only=True)

    class Meta:
        model = BudgetTemplate
        fields = '__all__'

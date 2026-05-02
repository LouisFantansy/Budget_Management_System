from rest_framework import serializers

from .models import BudgetTemplate, TemplateField
from .validation import validate_template_formula


class TemplateFieldSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        input_type = attrs.get('input_type', getattr(self.instance, 'input_type', TemplateField.InputType.TEXT))
        formula = attrs.get('formula', getattr(self.instance, 'formula', ''))
        if input_type == TemplateField.InputType.FORMULA:
            if not formula:
                raise serializers.ValidationError({'formula': '公式字段必须配置 formula。'})
            template = attrs.get('template', getattr(self.instance, 'template', None))
            field_proxy = self.instance or TemplateField(
                template=template,
                code=attrs.get('code', getattr(self.instance, 'code', '')),
                label=attrs.get('label', getattr(self.instance, 'label', '')),
                data_type=attrs.get('data_type', getattr(self.instance, 'data_type', TemplateField.DataType.MONEY)),
                input_type=input_type,
                formula=formula,
            )
            validate_template_formula(template, field_proxy, formula)
        return attrs

    class Meta:
        model = TemplateField
        fields = '__all__'


class BudgetTemplateSerializer(serializers.ModelSerializer):
    fields = TemplateFieldSerializer(many=True, read_only=True)

    class Meta:
        model = BudgetTemplate
        fields = '__all__'

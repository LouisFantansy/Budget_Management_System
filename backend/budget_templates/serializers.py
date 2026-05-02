from rest_framework import serializers

from accounts.access import can_manage_template_schema
from .access import can_user_edit_template_field, can_user_view_template_field, normalize_field_rules
from .models import BudgetTemplate, TemplateField
from .validation import validate_template_formula


class TemplateFieldSerializer(serializers.ModelSerializer):
    user_permissions = serializers.SerializerMethodField(read_only=True)

    def get_user_permissions(self, obj):
        user = getattr(self.context.get('request'), 'user', None)
        return {
            'visible': can_user_view_template_field(user, obj),
            'editable': can_user_edit_template_field(user, obj),
        }

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if 'visible_rules' in attrs:
            attrs['visible_rules'] = normalize_field_rules(attrs['visible_rules'], field_name='visible_rules')
        if 'editable_rules' in attrs:
            attrs['editable_rules'] = normalize_field_rules(attrs['editable_rules'], field_name='editable_rules')
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
    fields = serializers.SerializerMethodField(method_name='get_template_fields')

    def get_template_fields(self, obj):
        user = getattr(self.context.get('request'), 'user', None)
        fields = list(obj.fields.all())
        if not can_manage_template_schema(user):
            fields = [field for field in fields if can_user_view_template_field(user, field)]
        serializer = TemplateFieldSerializer(fields, many=True, context=self.context)
        return serializer.data

    class Meta:
        model = BudgetTemplate
        fields = '__all__'

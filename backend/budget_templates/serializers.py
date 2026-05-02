from rest_framework import serializers

from accounts.access import can_manage_template_schema
from masterdata.services import is_registered_option_source
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
        input_type = attrs.get('input_type', getattr(self.instance, 'input_type', TemplateField.InputType.TEXT))
        data_type = attrs.get('data_type', getattr(self.instance, 'data_type', TemplateField.DataType.TEXT))
        option_source = (attrs.get('option_source', getattr(self.instance, 'option_source', '')) or '').strip()
        import_aliases = attrs.get('import_aliases', getattr(self.instance, 'import_aliases', []))
        width = attrs.get('width', getattr(self.instance, 'width', 160))
        if 'visible_rules' in attrs:
            attrs['visible_rules'] = normalize_field_rules(attrs['visible_rules'], field_name='visible_rules')
        if 'editable_rules' in attrs:
            attrs['editable_rules'] = normalize_field_rules(attrs['editable_rules'], field_name='editable_rules')
        formula = attrs.get('formula', getattr(self.instance, 'formula', ''))

        if width <= 0:
            raise serializers.ValidationError({'width': '字段宽度必须大于 0。'})

        if input_type in {TemplateField.InputType.SELECT, TemplateField.InputType.MULTI_SELECT} and not option_source:
            raise serializers.ValidationError({'option_source': '下拉字段必须配置 option_source。'})
        if input_type in {
            TemplateField.InputType.SELECT,
            TemplateField.InputType.MULTI_SELECT,
            TemplateField.InputType.USER,
            TemplateField.InputType.DEPARTMENT,
            TemplateField.InputType.PROJECT,
        } and option_source and '|' not in option_source and not is_registered_option_source(option_source):
            raise serializers.ValidationError({'option_source': f'未注册的 option_source: {option_source}'})
        if input_type not in {TemplateField.InputType.SELECT, TemplateField.InputType.MULTI_SELECT}:
            attrs['option_source'] = ''

        if input_type in {TemplateField.InputType.USER, TemplateField.InputType.DEPARTMENT, TemplateField.InputType.PROJECT}:
            if data_type != TemplateField.DataType.OPTION:
                raise serializers.ValidationError({'data_type': '选择类字段的数据类型必须为 option。'})

        if not isinstance(import_aliases, list):
            raise serializers.ValidationError({'import_aliases': '导入别名必须为数组。'})
        normalized_aliases = []
        for alias in import_aliases:
            alias_text = str(alias).strip()
            if alias_text and alias_text not in normalized_aliases:
                normalized_aliases.append(alias_text)
        attrs['import_aliases'] = normalized_aliases

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
    copied_from_name = serializers.CharField(source='copied_from.name', read_only=True)

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

    def validate(self, attrs):
        attrs = super().validate(attrs)
        cycle = attrs.get('cycle', getattr(self.instance, 'cycle', None))
        expense_type = attrs.get('expense_type', getattr(self.instance, 'expense_type', None))
        schema_version = attrs.get('schema_version', getattr(self.instance, 'schema_version', 1))
        queryset = BudgetTemplate.objects.filter(cycle=cycle, expense_type=expense_type, schema_version=schema_version)
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        if queryset.exists():
            raise serializers.ValidationError({'schema_version': '同一周期和费用类型下 schema version 不能重复。'})
        return attrs

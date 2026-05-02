from rest_framework import serializers

from .models import Category, CostCenter, GLAccount, OptionSourceRegistryEntry, ProductLine, Project, ProjectCategory, PurchaseHistory, Region, Vendor


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class ProjectCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectCategory
        fields = '__all__'


class ProductLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductLine
        fields = '__all__'


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = '__all__'


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = '__all__'


class CostCenterSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = CostCenter
        fields = '__all__'


class GLAccountSerializer(serializers.ModelSerializer):
    mapped_category_name = serializers.CharField(source='mapped_category.name', read_only=True)
    mapped_project_category_name = serializers.CharField(source='mapped_project_category.name', read_only=True)

    class Meta:
        model = GLAccount
        fields = '__all__'


class OptionSourceRegistryEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = OptionSourceRegistryEntry
        fields = '__all__'


class PurchaseHistorySerializer(serializers.ModelSerializer):
    recommended_price = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = PurchaseHistory
        fields = '__all__'

from rest_framework import decorators, response, viewsets

from .models import Category, ProductLine, Project, ProjectCategory, PurchaseHistory, Region, Vendor
from .serializers import (
    CategorySerializer,
    ProductLineSerializer,
    ProjectCategorySerializer,
    ProjectSerializer,
    PurchaseHistorySerializer,
    RegionSerializer,
    VendorSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.select_related('parent').all()
    serializer_class = CategorySerializer
    filterset_fields = ['level', 'parent', 'is_active']
    search_fields = ['name', 'code']


class ProjectCategoryViewSet(viewsets.ModelViewSet):
    queryset = ProjectCategory.objects.all()
    serializer_class = ProjectCategorySerializer
    search_fields = ['name', 'code']


class ProductLineViewSet(viewsets.ModelViewSet):
    queryset = ProductLine.objects.all()
    serializer_class = ProductLineSerializer
    search_fields = ['name', 'code']


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.select_related('project_category', 'product_line').all()
    serializer_class = ProjectSerializer
    filterset_fields = ['project_category', 'product_line', 'is_active']
    search_fields = ['name', 'code']


class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    search_fields = ['name', 'code']


class RegionViewSet(viewsets.ModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    search_fields = ['name', 'code']


class PurchaseHistoryViewSet(viewsets.ModelViewSet):
    queryset = PurchaseHistory.objects.select_related('vendor', 'category').all()
    serializer_class = PurchaseHistorySerializer
    search_fields = ['purchase_name']

    @decorators.action(detail=False, methods=['get'])
    def suggest(self, request):
        query = request.query_params.get('q', '').strip()
        queryset = self.get_queryset()
        if query:
            queryset = queryset.filter(purchase_name__icontains=query)
        serializer = self.get_serializer(queryset[:10], many=True)
        return response.Response(serializer.data)

# Create your views here.

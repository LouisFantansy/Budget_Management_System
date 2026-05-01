from rest_framework import viewsets

from .models import Department
from .serializers import DepartmentSerializer


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.select_related('parent').all()
    serializer_class = DepartmentSerializer
    filterset_fields = ['level', 'parent', 'is_active']
    search_fields = ['name', 'code', 'cost_center_code']

# Create your views here.

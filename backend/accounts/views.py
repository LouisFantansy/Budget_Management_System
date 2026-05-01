from rest_framework import viewsets

from .models import RoleAssignment, User
from .serializers import RoleAssignmentSerializer, UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    search_fields = ['username', 'display_name', 'employee_id', 'email']


class RoleAssignmentViewSet(viewsets.ModelViewSet):
    queryset = RoleAssignment.objects.select_related('user', 'department').all()
    serializer_class = RoleAssignmentSerializer
    filterset_fields = ['role', 'department', 'is_primary']

# Create your views here.

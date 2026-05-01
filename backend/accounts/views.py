from django.contrib.auth import authenticate, login, logout
from rest_framework import decorators, permissions, response, status, viewsets

from .models import RoleAssignment, User
from .serializers import LoginSerializer, RoleAssignmentSerializer, UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    search_fields = ['username', 'display_name', 'employee_id', 'email']


class RoleAssignmentViewSet(viewsets.ModelViewSet):
    queryset = RoleAssignment.objects.select_related('user', 'department').all()
    serializer_class = RoleAssignmentSerializer
    filterset_fields = ['role', 'department', 'is_primary']

# Create your views here.


@decorators.api_view(['POST'])
@decorators.permission_classes([permissions.AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(
        request,
        username=serializer.validated_data['username'],
        password=serializer.validated_data['password'],
    )
    if not user:
        return response.Response({'detail': '用户名或密码错误。'}, status=status.HTTP_400_BAD_REQUEST)
    login(request, user)
    return response.Response(UserSerializer(user).data)


@decorators.api_view(['POST'])
def logout_view(request):
    logout(request)
    return response.Response(status=status.HTTP_204_NO_CONTENT)


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
def me_view(request):
    return response.Response(UserSerializer(request.user).data)

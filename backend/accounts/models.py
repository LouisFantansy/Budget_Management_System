from django.contrib.auth.models import AbstractUser
from django.db import models

from common.models import TimestampedModel


class User(AbstractUser):
    employee_id = models.CharField('工号', max_length=64, blank=True)
    display_name = models.CharField('显示名称', max_length=128, blank=True)
    primary_department = models.ForeignKey(
        'orgs.Department',
        verbose_name='主部门',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_users',
    )

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'

    def __str__(self):
        return self.display_name or self.username


class RoleAssignment(TimestampedModel):
    class Role(models.TextChoices):
        ENGINEER = 'engineer', '一线工程师'
        SECONDARY_BUDGET_ADMIN = 'secondary_budget_admin', '二级部门次预算管理员'
        SECONDARY_BUDGET_OWNER = 'secondary_budget_owner', '二级部门主预算管理员'
        SECONDARY_DEPT_HEAD = 'secondary_dept_head', '二级部门负责人'
        PRIMARY_BUDGET_ADMIN = 'primary_budget_admin', '一级部门预算管理员'
        PRIMARY_BUDGET_REVIEWER = 'primary_budget_reviewer', '一级预算管理员主管/主办'
        PRIMARY_DEPT_HEAD = 'primary_dept_head', '一级部门负责人'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='role_assignments')
    role = models.CharField(max_length=64, choices=Role.choices)
    department = models.ForeignKey(
        'orgs.Department',
        on_delete=models.CASCADE,
        related_name='role_assignments',
        null=True,
        blank=True,
        help_text='为空表示全局角色；不为空表示仅在该部门范围生效。',
    )
    is_primary = models.BooleanField(default=False)

    class Meta:
        verbose_name = '角色授权'
        verbose_name_plural = '角色授权'
        unique_together = [('user', 'role', 'department')]

    def __str__(self):
        scope = self.department.name if self.department else '全局'
        return f'{self.user} - {self.get_role_display()} - {scope}'

# Create your models here.

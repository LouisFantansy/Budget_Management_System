from django.db import models

from common.models import TimestampedModel


class Department(TimestampedModel):
    class Level(models.TextChoices):
        PRIMARY = 'primary', '一级部门'
        SECONDARY = 'secondary', '二级部门'
        SECTION = 'section', 'Section'
        SS_PUBLIC = 'ss_public', 'SS public'

    name = models.CharField(max_length=128)
    code = models.CharField(max_length=64, unique=True)
    level = models.CharField(max_length=32, choices=Level.choices)
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='children',
    )
    cost_center_code = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = '部门'
        verbose_name_plural = '部门'
        ordering = ['sort_order', 'code']

    def __str__(self):
        return self.name

# Create your models here.

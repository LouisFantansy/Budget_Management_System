from decimal import Decimal

from django.db import models

from common.models import TimestampedModel


class NamedMasterData(TimestampedModel):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ['sort_order', 'code']

    def __str__(self):
        return self.name


class Category(NamedMasterData):
    class Level(models.TextChoices):
        CATEGORY = 'category', 'Category'
        L1 = 'l1', 'Category L1'
        L2 = 'l2', 'Category L2'

    level = models.CharField(max_length=16, choices=Level.choices)
    parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='children')

    class Meta(NamedMasterData.Meta):
        verbose_name = '预算分类'
        verbose_name_plural = '预算分类'


class ProjectCategory(NamedMasterData):
    class Meta(NamedMasterData.Meta):
        verbose_name = '项目类别'
        verbose_name_plural = '项目类别'


class ProductLine(NamedMasterData):
    class Meta(NamedMasterData.Meta):
        verbose_name = '产品线'
        verbose_name_plural = '产品线'


class Project(NamedMasterData):
    project_category = models.ForeignKey(ProjectCategory, on_delete=models.PROTECT, null=True, blank=True)
    product_line = models.ForeignKey(ProductLine, on_delete=models.PROTECT, null=True, blank=True)

    class Meta(NamedMasterData.Meta):
        verbose_name = '项目'
        verbose_name_plural = '项目'


class Vendor(NamedMasterData):
    class Meta(NamedMasterData.Meta):
        verbose_name = '供应商'
        verbose_name_plural = '供应商'


class Region(NamedMasterData):
    class Meta(NamedMasterData.Meta):
        verbose_name = '地区'
        verbose_name_plural = '地区'


class PurchaseHistory(TimestampedModel):
    purchase_name = models.CharField(max_length=255, db_index=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    deal_price = models.DecimalField(max_digits=14, decimal_places=2)
    deal_date = models.DateField(null=True, blank=True)
    source = models.CharField(max_length=128, blank=True)

    class Meta:
        verbose_name = '历史采购记录'
        verbose_name_plural = '历史采购记录'
        ordering = ['-deal_date', 'purchase_name']

    @property
    def recommended_price(self):
        return (self.deal_price * Decimal('1.2')).quantize(Decimal('0.01'))

    def __str__(self):
        return self.purchase_name

# Create your models here.

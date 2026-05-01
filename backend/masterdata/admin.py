from django.contrib import admin

from .models import Category, ProductLine, Project, ProjectCategory, PurchaseHistory, Region, Vendor


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'level', 'parent', 'is_active')
    list_filter = ('level', 'is_active')
    search_fields = ('name', 'code')


admin.site.register(ProjectCategory)
admin.site.register(ProductLine)
admin.site.register(Project)
admin.site.register(Vendor)
admin.site.register(Region)


@admin.register(PurchaseHistory)
class PurchaseHistoryAdmin(admin.ModelAdmin):
    list_display = ('purchase_name', 'vendor', 'category', 'deal_price', 'deal_date', 'recommended_price')
    search_fields = ('purchase_name', 'vendor__name')
    list_filter = ('category',)

# Register your models here.

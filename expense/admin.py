from django.contrib import admin
from .models import ShippingExpense, ServicingExpense, MiscellaneousExpense


@admin.register(ShippingExpense)
class ShippingExpenseAdmin(admin.ModelAdmin):
    list_display = ("sale", "cost", "description", "date", "created_at")
    search_fields = ("sale__id", "description")
    list_filter = ("date",)


@admin.register(ServicingExpense)
class ServicingExpenseAdmin(admin.ModelAdmin):
    list_display = ("product", "cost", "description", "date", "created_at")
    search_fields = ("product__name", "description")
    list_filter = ("date",)


@admin.register(MiscellaneousExpense)
class MiscellaneousExpenseAdmin(admin.ModelAdmin):
    list_display = ("cost", "description", "date", "created_at")
    search_fields = ("description",)
    list_filter = ("date",)

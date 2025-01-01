from django.contrib import admin
from .models import Sale


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity_sold", "sale_price", "sale_date")
    search_fields = ("product__name", "customer_name")
    list_filter = ("shipping_status", "sale_date")

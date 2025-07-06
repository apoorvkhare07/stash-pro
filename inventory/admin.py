from django.contrib import admin
from .models import Product, Lot


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "price", "available_quantity")
    search_fields = ("name", "category", "sub_category")
    list_filter = ("category", "sub_category")


@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "total_price", "bought_on", "paid_on", "bought_from")
    search_fields = ("title", "bought_from")
    list_filter = ("bought_on", "paid_on")
    date_hierarchy = "bought_on"  # Adds date-based navigation
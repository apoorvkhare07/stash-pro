from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "sub_category", "price", "stock")
    search_fields = ("name", "category", "sub_category")
    list_filter = ("category", "sub_category")
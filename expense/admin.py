from django.contrib import admin
from .models import Expenses


@admin.register(Expenses)
class ExpensesAdmin(admin.ModelAdmin):
    list_display = ("type", "amount", "vendor", "sale", "product", "description", "date", "created_at")
    search_fields = ("description", "vendor", "sale__id", "product__name")
    list_filter = ("type", "date", "created_at")
    readonly_fields = ("date", "created_at", "updated_at")
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("type", "amount", "description", "vendor")
        }),
        ("Related Objects", {
            "fields": ("sale", "product"),
            "description": "Associate with Sale (for shipping/refund) or Product (for servicing)"
        }),
        ("Timestamps", {
            "fields": ("date", "created_at", "updated_at"),
            "classes": ("collapse",)
        })
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Add help text for type field
        if 'type' in form.base_fields:
            form.base_fields['type'].help_text = (
                "Shipping/Refund: Requires Sale association. "
                "Servicing: Requires Product association. "
                "Miscellaneous: No association required."
            )
        return form
    
    def get_queryset(self, request):
        # Optimize queries by selecting related objects
        return super().get_queryset(request).select_related('sale', 'product')
    
    # Custom methods for better display
    def get_readonly_fields(self, request, obj=None):
        # Make date readonly always, but allow editing other fields
        return self.readonly_fields

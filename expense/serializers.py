from rest_framework import serializers
from .models import Expenses
from decimal import Decimal


class ExpensesSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    sale_details = serializers.SerializerMethodField()
    product_details = serializers.SerializerMethodField()

    class Meta:
        model = Expenses
        fields = "__all__"
        read_only_fields = ('date', 'created_at', 'updated_at')

    def get_sale_details(self, obj):
        if obj.sale:
            return {
                'id': obj.sale.id,
                'product_name': obj.sale.product.name,
                'customer': obj.sale.customer
            }
        return None

    def get_product_details(self, obj):
        if obj.product:
            return {
                'id': obj.product.id,
                'name': obj.product.name
            }
        return None

    def validate_amount(self, value):
        if value is None:
            raise serializers.ValidationError("Amount is required")
        try:
            amount = Decimal(str(value))
            if amount <= 0:
                raise serializers.ValidationError("Amount must be greater than 0")
            return amount
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid amount format")

    def validate_type(self, value):
        if value not in dict(Expenses.ExpenseType.choices):
            raise serializers.ValidationError("Invalid expense type")
        return value

    def validate(self, data):
        # sale and product are optional - use them when provided
        return data

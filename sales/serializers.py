from rest_framework import serializers
from decimal import Decimal
from inventory.serializers import ProductTitleSerializer
from .models import Sale
from inventory.models import Product
from django.utils.timezone import now
from django.db import transaction


class SaleSerializer(serializers.ModelSerializer):
    product_details = ProductTitleSerializer(source='product', read_only=True)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), write_only=True)
    days_since_sale = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = ('id', 'product', 'product_details', 'quantity_sold', 'sale_price', 'customer', 'sale_date', 'shipping_status', 'days_since_sale', 'created_at', 'updated_at')
        read_only_fields = ('shipping_status', 'created_at', 'updated_at')
        extra_kwargs = {
            'product': {'required': True},
            'quantity_sold': {'required': True},
            'sale_price': {'required': True},
            'sale_date': {'required': True},
        }

    def get_days_since_sale(self, obj):
        """
        Calculate and format the number of days since the sale was created.
        """
        days = (now() - obj.created_at).days
        return days

    def validate_product(self, value):
        if not value:
            raise serializers.ValidationError("Product is required")
        return value

    def validate_quantity_sold(self, value):
        if value is None:
            raise serializers.ValidationError("Quantity sold is required")
        try:
            quantity = int(value)
            if quantity <= 0:
                raise serializers.ValidationError("Quantity sold must be greater than 0")
            return quantity
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid quantity format")

    def validate_sale_price(self, value):
        if value is None:
            raise serializers.ValidationError("Sale price is required")
        try:
            price = Decimal(str(value))
            if price <= 0:
                raise serializers.ValidationError("Sale price must be greater than 0")
            return price
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid sale price format")

    def validate_sale_date(self, value):
        if not value:
            raise serializers.ValidationError("Sale date is required")
        return value

    def validate(self, data):
        # Check required fields
        if not data.get('product'):
            raise serializers.ValidationError({"product": "Product is required"})
        if not data.get('quantity_sold'):
            raise serializers.ValidationError({"quantity_sold": "Quantity sold is required"})
        if not data.get('sale_price'):
            raise serializers.ValidationError({"sale_price": "Sale price is required"})
        if not data.get('sale_date'):
            raise serializers.ValidationError({"sale_date": "Sale date is required"})

        # Validate product availability
        product = data.get('product')
        quantity_sold = data.get('quantity_sold')
        if product and quantity_sold:
            if product.available_quantity < quantity_sold:
                raise serializers.ValidationError(
                    {"quantity_sold": f"Only {product.available_quantity} units available"}
                )

        # Always set shipping_status to pending for new sales
        data['shipping_status'] = Sale.ShippingStatus.SHIPPING_PENDING
        return data

    def create(self, validated_data):
        with transaction.atomic():
            # Get product and quantity from validated data
            product = validated_data.get('product')
            quantity_sold = validated_data.get('quantity_sold')

            # Create the sale object
            sale = Sale.objects.create(**validated_data)

            # Update product's available quantity
            product.available_quantity -= quantity_sold
            product.save()

            return sale
from rest_framework import serializers
from decimal import Decimal
from inventory.serializers import ProductTitleSerializer
from .models import Sale, ShippingInfo
from inventory.models import Product
from django.utils.timezone import now
from django.db import transaction


class SaleSerializer(serializers.ModelSerializer):
    product_details = ProductTitleSerializer(source='product', read_only=True)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    days_since_sale = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = ('id', 'product', 'product_details', 'quantity_sold', 'sale_price', 'customer', 'sale_date', 'shipping_status', 'is_refunded', 'refunded_at', 'days_since_sale', 'created_at', 'updated_at')
        read_only_fields = ('is_refunded', 'refunded_at', 'created_at', 'updated_at')
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
        instance = self.instance  # Will be None for create, Sale object for update
        
        # For create, all fields are required
        if not instance:
            if not data.get('product'):
                raise serializers.ValidationError({"product": "Product is required"})
            if not data.get('quantity_sold'):
                raise serializers.ValidationError({"quantity_sold": "Quantity sold is required"})
            if not data.get('sale_price'):
                raise serializers.ValidationError({"sale_price": "Sale price is required"})
            if not data.get('sale_date'):
                raise serializers.ValidationError({"sale_date": "Sale date is required"})

        # Validate product availability
        product = data.get('product', instance.product if instance else None)
        quantity_sold = data.get('quantity_sold', instance.quantity_sold if instance else None)
        
        if product and quantity_sold:
            available = product.available_quantity
            # For updates, add back the original quantity if same product
            if instance and instance.product == product:
                available += instance.quantity_sold
            
            if available < quantity_sold:
                raise serializers.ValidationError(
                    {"quantity_sold": f"Only {available} units available"}
                )

        # Set shipping_status to pending only for new sales
        if not instance:
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

    def update(self, instance, validated_data):
        with transaction.atomic():
            old_product = instance.product
            old_quantity = instance.quantity_sold
            
            new_product = validated_data.get('product', old_product)
            new_quantity = validated_data.get('quantity_sold', old_quantity)
            
            # Restore old product's quantity
            old_product.available_quantity += old_quantity
            old_product.save()
            
            # Deduct from new product's quantity
            new_product.available_quantity -= new_quantity
            new_product.save()
            
            # Update the sale
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            
            return instance



class ShippingInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingInfo
        fields = ('id', 'customer_name', 'customer_email', 'customer_phone', 'customer_address', 'customer_pincode')
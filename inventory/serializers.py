from rest_framework import serializers
from .models import Product, Lot, Payment
from decimal import Decimal
import datetime


class ProductSerializer(serializers.ModelSerializer):
    bought_at = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = "__all__"
        read_only_fields = ('available_quantity',)
        extra_kwargs = {
            'name': {'required': True},
            'price': {'required': True},
            'stock': {'required': True},
        }

    def get_bought_at(self, obj):
        """
        Get the bought_at date from the associated lot's bought_on field
        """
        if obj.lot and obj.lot.bought_on:
            return obj.lot.bought_on.strftime("%d-%m-%Y")
        return None

    def get_status(self, obj):
        if obj.available_quantity <= 0:
            return "Sold"
        else:
            return "Available"

    def validate_price(self, value):
        if value is None:
            raise serializers.ValidationError("Price is required")
        try:
            price = Decimal(str(value))
            if price <= 0:
                raise serializers.ValidationError("Price must be greater than 0")
            return price
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid price format")

    def validate_stock(self, value):
        if value is None:
            raise serializers.ValidationError("Stock is required")
        try:
            stock = int(value)
            if stock <= 0:
                raise serializers.ValidationError("Stock must be greater than 0")
            return stock
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid stock format")

    def validate_category(self, value):
        if value and value not in dict(Product.Category.choices):
            raise serializers.ValidationError("Invalid category choice")
        return value

    def validate_sub_category(self, value):
        if value and value not in dict(Product.SubCategory.choices):
            raise serializers.ValidationError("Invalid sub_category choice")
        return value

    def validate_cosmetic_condition(self, value):
        if value and value not in dict(Product.CosmeticCondition.choices):
            raise serializers.ValidationError("Invalid cosmetic_condition choice")
        return value

    def validate_working_condition(self, value):
        if value and value not in dict(Product.WorkingCondition.choices):
            raise serializers.ValidationError("Invalid working_condition choice")
        return value

    def validate_delivery_status(self, value):
        if value and value not in dict(Product.DeliveryStatus.choices):
            raise serializers.ValidationError("Invalid delivery_status choice")
        return value

    def validate(self, data):
        # Check required fields
        if not data.get('name'):
            raise serializers.ValidationError({"name": "Name is required"})
        if not data.get('price'):
            raise serializers.ValidationError({"price": "Price is required"})
        if not data.get('stock'):
            raise serializers.ValidationError({"stock": "Stock is required"})
        if not data.get('lot'):
            raise serializers.ValidationError({"lot": "Lot is required"})

        # Set available_quantity equal to stock for new products
        if 'stock' in data:
            data['available_quantity'] = data['stock']
        return data


class ProductTitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name")


class LotSerializer(serializers.ModelSerializer):
    products = ProductTitleSerializer(many=True, read_only=True)
    bought_on = serializers.DateField(format="%Y-%m-%d")

    class Meta:
        model = Lot
        fields = "__all__"
        read_only_fields = ('created_at', 'updated_at')

    def validate_total_price(self, value):
        if value is None:
            raise serializers.ValidationError("Total price is required")
        try:
            price = Decimal(str(value))
            if price <= 0:
                raise serializers.ValidationError("Total price must be greater than 0")
            return price
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid total price format")


class PaymentSerializer(serializers.ModelSerializer):
    lot_title = serializers.CharField(source='lot.title', read_only=True)
    payment_date = serializers.DateField(format="%Y-%m-%d")

    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ('created_at', 'updated_at')

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

    def validate(self, data):
        if not data.get('lot'):
            raise serializers.ValidationError({"lot": "Lot is required"})
        if not data.get('payment_date'):
            raise serializers.ValidationError({"payment_date": "Payment date is required"})
        return data


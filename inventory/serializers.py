from rest_framework import serializers
from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    bought_at = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = "__all__"

    def get_bought_at(self, obj):
        if obj.bought_at:
            return obj.bought_at.strftime("%d-%m-%Y")
        return None

    def get_status(self, obj):
        if obj.available_quantity <= 0:
            return "Sold"
        else:
            return "Available"


class ProductTitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name")


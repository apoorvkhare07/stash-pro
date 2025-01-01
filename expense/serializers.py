from rest_framework import serializers
from .models import ShippingExpense, ServicingExpense, MiscellaneousExpense


class ShippingExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingExpense
        fields = "__all__"


class ServicingExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicingExpense
        fields = "__all__"


class MiscellaneousExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = MiscellaneousExpense
        fields = "__all__"

from rest_framework import serializers

from inventory.serializers import ProductTitleSerializer
from .models import Sale


class SaleSerializer(serializers.ModelSerializer):
    product = ProductTitleSerializer()
    days_since_sale = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = "__all__"

    def get_days_since_sale(self, obj):
        """
        Calculate and format the number of days since the sale date.
        """
        days = obj.days_since_sale.total_seconds() // (24 * 3600)  # Convert duration to days
        return int(days)
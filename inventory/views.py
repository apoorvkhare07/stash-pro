import datetime

from rest_framework.decorators import action
from rest_framework import viewsets
from .models import Product
from .serializers import ProductSerializer
from rest_framework.response import Response


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    @action(detail=False, methods=["get"])
    def overview(self, request):
        # Calculate total unsold inventory
        total_unsold_inventory = Product.objects.filter(available_quantity__gt=0).count()

        # Get all unsold items
        unsold_items = Product.objects.filter(available_quantity__gt=0).values("id", "name", "available_quantity")

        # Calculate unsold items bought this month
        start_of_month = datetime.datetime.now().replace(day=1)
        unsold_items_bought_this_month = Product.objects.filter(
            available_quantity__gt=0,
            created_at__gte=start_of_month
        ).count()

        # Construct the response
        data = {
            "total_unsold_inventory": total_unsold_inventory,
            "unsold_items": list(unsold_items),  # Convert QuerySet to list of dictionaries
            "unsold_items_bought_this_month": unsold_items_bought_this_month,
        }

        return Response(data)
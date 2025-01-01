from rest_framework.decorators import action
from rest_framework import viewsets
from .models import Sale
from .serializers import SaleSerializer
from rest_framework.response import Response
from django.db.models import Sum, F, ExpressionWrapper, DurationField
from django.utils.timezone import now


class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer

    @action(detail=False, methods=["get"])
    def unshipped(self, request):
        """
        Returns all unshipped sale items.
        """
        unshipped_sales = Sale.objects.filter(shipping_status=Sale.ShippingStatus.SHIPPING_PENDING).annotate(
            days_since_sale=ExpressionWrapper(
                now() - F('sale_date'), output_field=DurationField()
            )
        ).order_by('-days_since_sale')

        # Total unshipped items
        total_unshipped_items = unshipped_sales.aggregate(total_items=Sum('quantity_sold'))['total_items'] or 0

        # Serialize the data
        serializer = self.get_serializer(unshipped_sales, many=True)

        response_data = {
            "total_unshipped_items": total_unshipped_items,
            "sales": serializer.data,
        }

        return Response(response_data)



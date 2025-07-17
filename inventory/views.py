import datetime
from rest_framework.decorators import action
from rest_framework import viewsets, status
from .models import Product, Lot, Payment
from .serializers import ProductSerializer, LotSerializer, PaymentSerializer
from rest_framework.response import Response
from sales.models import Sale
from django_filters import rest_framework as filters


class ProductFilter(filters.FilterSet):
    status = filters.CharFilter(method='filter_status')

    class Meta:
        model = Product
        fields = ['status']

    def filter_status(self, queryset, name, value):
        if value.lower() == 'sold':
            return queryset.filter(available_quantity=0)
        elif value.lower() == 'available':
            return queryset.filter(available_quantity__gt=0)
        return queryset


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = ProductFilter

    @action(detail=True, methods=["post"])
    def mark_as_sold(self, request, pk=None):
        product = self.get_object()
        quantity = request.data.get('quantity', 1)
        sale_price = request.data.get('sale_price', product.price)
        customer = request.data.get('customer', None)

        if product.available_quantity < quantity:
            return Response(
                {"error": f"Only {product.available_quantity} units available"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create sale record
        Sale.objects.create(
            product=product,
            quantity_sold=quantity,
            sale_price=sale_price,
            customer=customer,
            sale_date=datetime.datetime.now(),
            shipping_status=Sale.ShippingStatus.SHIPPING_PENDING
        )

        # Update product quantity
        product.available_quantity -= quantity
        product.save()

        return Response({"message": f"Successfully marked {quantity} unit(s) as sold"})

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


class LotViewSet(viewsets.ModelViewSet):
    queryset = Lot.objects.all()
    serializer_class = LotSerializer

    def get_queryset(self):
        queryset = Lot.objects.all()
        # Add any filtering if needed
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    
    def get_queryset(self):
        queryset = Payment.objects.all()
        # Filter by lot if provided
        lot_id = self.request.query_params.get('lot', None)
        if lot_id:
            queryset = queryset.filter(lot=lot_id)
        return queryset
    
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            print(request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

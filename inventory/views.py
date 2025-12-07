import datetime
from rest_framework.decorators import action
from rest_framework import viewsets, status
from .models import Product, Lot, Payment
from .serializers import ProductSerializer, LotSerializer, PaymentSerializer
from rest_framework.response import Response
from sales.models import Sale
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from django.utils.timezone import make_aware


class ProductFilter(filters.FilterSet):
    status = filters.CharFilter(method='filter_status')
    start_date = filters.DateFilter(method='filter_start_date')
    end_date = filters.DateFilter(method='filter_end_date')

    class Meta:
        model = Product
        fields = ['status', 'start_date', 'end_date']

    def filter_status(self, queryset, name, value):
        if value.lower() == 'sold':
            return queryset.filter(available_quantity=0)
        elif value.lower() == 'available':
            return queryset.filter(available_quantity__gt=0)
        return queryset

    def filter_start_date(self, queryset, name, value):
        """Filter products bought on or after the start date"""
        if value:
            # Convert date to timezone-aware datetime at start of day
            start_datetime = make_aware(datetime.datetime.combine(value, datetime.time.min))
            return queryset.filter(bought_at__gte=start_datetime)
        return queryset

    def filter_end_date(self, queryset, name, value):
        """Filter products bought on or before the end date"""
        if value:
            # Convert date to timezone-aware datetime at end of day
            end_datetime = make_aware(datetime.datetime.combine(value, datetime.time.max))
            return queryset.filter(bought_at__lte=end_datetime)
        return queryset


class LotFilter(filters.FilterSet):
    start_date = filters.DateFilter(field_name='bought_on', lookup_expr='gte')
    end_date = filters.DateFilter(field_name='bought_on', lookup_expr='lte')
    status = filters.CharFilter(field_name='status')

    class Meta:
        model = Lot
        fields = ['start_date', 'end_date', 'status']


class PaymentFilter(filters.FilterSet):
    start_date = filters.DateFilter(field_name='payment_date', lookup_expr='gte')
    end_date = filters.DateFilter(field_name='payment_date', lookup_expr='lte')
    lot = filters.NumberFilter(field_name='lot')

    class Meta:
        model = Payment
        fields = ['start_date', 'end_date', 'lot']


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = ProductFilter

    @extend_schema(
        summary="Mark product as sold",
        description="Creates a sale record and decreases product quantity",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'quantity': {'type': 'integer', 'default': 1},
                    'sale_price': {'type': 'number'},
                    'customer': {'type': 'string'},
                },
                'example': {'quantity': 1, 'sale_price': 299.99, 'customer': 'John Doe'}
            }
        },
        responses={200: {'description': 'Successfully marked as sold'}},
    )
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

    @extend_schema(
        summary="Get inventory overview",
        description="Returns total unsold inventory count and list of unsold items",
    )
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
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = LotFilter

    def get_queryset(self):
        return Lot.objects.all().order_by('-bought_on')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = PaymentFilter
    
    def get_queryset(self):
        return Payment.objects.all().order_by('-payment_date')
    
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

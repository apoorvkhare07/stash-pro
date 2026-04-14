import datetime
from rest_framework.decorators import action
from rest_framework import viewsets, status, serializers
from rest_framework.views import APIView
from .models import Product, Lot, Payment
from .serializers import ProductSerializer, LotSerializer, PaymentSerializer
from rest_framework.response import Response
from sales.models import Sale
from django_filters import rest_framework as filters
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import HasModelPermission, IsOwnerGroup
from accounts.mixins import OrgQuerysetMixin
from django.db import transaction


class ProductFilter(filters.FilterSet):
    status = filters.CharFilter(method='filter_status')
    start_date = filters.DateFilter(field_name='lot__bought_on', lookup_expr='gte')
    end_date = filters.DateFilter(field_name='lot__bought_on', lookup_expr='lte')

    class Meta:
        model = Product
        fields = ['status', 'start_date', 'end_date']

    def filter_status(self, queryset, name, value):
        if value.lower() == 'sold':
            return queryset.filter(available_quantity=0)
        elif value.lower() == 'available':
            return queryset.filter(available_quantity__gt=0)
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


class ProductViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, HasModelPermission]

    filter_backends = (filters.DjangoFilterBackend, SearchFilter, OrderingFilter)

    def get_queryset(self):
        return super().get_queryset().select_related('lot')
    filterset_class = ProductFilter
    search_fields = ['name', 'specs']
    ordering_fields = ['id', 'name', 'price', 'available_quantity', 'created_at']
    ordering = ['id']

    def update(self, request, *args, **kwargs):
        """
        Update a product. If stock changes, adjust available_quantity accordingly.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        old_stock = instance.stock
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # Calculate stock difference and adjust available_quantity
        new_stock = serializer.validated_data.get('stock', old_stock)
        stock_diff = new_stock - old_stock
        
        self.perform_update(serializer)
        
        # Adjust available_quantity based on stock change
        if stock_diff != 0:
            instance.available_quantity = max(0, instance.available_quantity + stock_diff)
            instance.save()
        
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        Delete a product. Only allowed if no sales exist for this product.
        """
        instance = self.get_object()
        
        # Check if product has any sales
        if instance.sales.exists():
            return Response(
                {"error": "Cannot delete product with existing sales. Delete the sales first."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

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
        qs = self.get_queryset()
        total_unsold_inventory = qs.filter(available_quantity__gt=0).count()

        unsold_items = qs.filter(available_quantity__gt=0).values("id", "name", "available_quantity")

        start_of_month = datetime.datetime.now().replace(day=1)
        unsold_items_bought_this_month = qs.filter(
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


class LotViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = Lot.objects.all()
    serializer_class = LotSerializer
    permission_classes = [IsAuthenticated, HasModelPermission]
    filter_backends = (filters.DjangoFilterBackend, OrderingFilter)
    filterset_class = LotFilter
    ordering_fields = ['id', 'bought_on', 'total_price']
    ordering = ['-bought_on']

    def get_queryset(self):
        return super().get_queryset().prefetch_related('payments', 'products').order_by('-bought_on')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        """
        Delete a lot. Only allowed if no products exist for this lot.
        """
        instance = self.get_object()
        
        # Check if lot has any products
        if instance.products.exists():
            return Response(
                {"error": "Cannot delete lot with existing products. Delete the products first."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, HasModelPermission]
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = PaymentFilter
    
    def get_queryset(self):
        qs = Payment.objects.all().order_by('-payment_date')
        org = getattr(self.request, 'organization', None)
        if org:
            qs = qs.filter(lot__organization=org)
        return qs
    
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except serializers.ValidationError:
            raise
        except Exception:
            return Response({"error": "Failed to create payment"}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        """
        Update a payment and recalculate lot payment status.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Update lot payment status
        instance.lot.update_payment_status()
        
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        Delete a payment and update the lot's payment status.
        """
        instance = self.get_object()
        lot = instance.lot
        
        # Delete the payment
        self.perform_destroy(instance)
        
        # Update lot payment status
        lot.update_payment_status()

        return Response(status=status.HTTP_204_NO_CONTENT)


class BulkImportView(APIView):
    """
    Bulk import lots with their products from sheet data.

    Expected JSON format:
    {
        "lots": [
            {
                "title": "Lot from seller X",
                "total_price": 50000,
                "bought_on": "2025-01-15",
                "bought_from": "Seller Name",
                "status": "paid",
                "products": [
                    {
                        "name": "Canon AE-1",
                        "price": 15000,
                        "stock": 1,
                        "category": "Film Camera",
                        "sub_category": "SLR",
                        "cosmetic_condition": "good",
                        "working_condition": "fully_working",
                        "specs": "35mm SLR, FD mount"
                    }
                ]
            }
        ],
        "sales": [
            {
                "product_name": "Canon AE-1",
                "quantity_sold": 1,
                "sale_price": 18000,
                "customer": "John",
                "sale_date": "2025-02-01",
                "shopify_order_id": "12345",
                "shopify_order_name": "#1001"
            }
        ]
    }
    """
    permission_classes = [IsAuthenticated, IsOwnerGroup]

    @transaction.atomic
    def post(self, request):
        org = getattr(request, 'organization', None)
        lots_data = request.data.get('lots', [])
        sales_data = request.data.get('sales', [])

        created_lots = 0
        created_products = 0
        created_sales = 0
        errors = []
        product_map = {}  # name -> product for sale matching

        # Import lots and products
        for i, lot_data in enumerate(lots_data):
            try:
                products_data = lot_data.pop('products', [])

                bought_on = lot_data.get('bought_on')
                if isinstance(bought_on, str):
                    lot_data['bought_on'] = datetime.datetime.strptime(bought_on, '%Y-%m-%d').date()

                paid_on = lot_data.get('paid_on')
                if isinstance(paid_on, str):
                    lot_data['paid_on'] = datetime.datetime.strptime(paid_on, '%Y-%m-%d').date()

                lot = Lot.objects.create(organization=org, **lot_data)
                created_lots += 1

                for j, prod_data in enumerate(products_data):
                    try:
                        stock = prod_data.get('stock', 1)
                        prod_data['available_quantity'] = stock
                        prod_data['lot'] = lot
                        product = Product.objects.create(organization=org, **prod_data)
                        created_products += 1
                        product_map[product.name.lower().strip()] = product
                    except Exception as e:
                        errors.append(f"Lot {i} Product {j}: {str(e)}")
            except Exception as e:
                errors.append(f"Lot {i}: {str(e)}")

        # Import sales
        for i, sale_data in enumerate(sales_data):
            try:
                product_name = sale_data.pop('product_name', '').lower().strip()
                product = product_map.get(product_name)

                if not product:
                    product = Product.objects.filter(name__iexact=product_name.strip()).first()

                if not product:
                    errors.append(f"Sale {i}: No product found matching '{product_name}'")
                    continue

                sale_date = sale_data.get('sale_date')
                if isinstance(sale_date, str):
                    sale_data['sale_date'] = datetime.datetime.strptime(sale_date, '%Y-%m-%d')

                sale = Sale.objects.create(
                    organization=org,
                    product=product,
                    quantity_sold=sale_data.get('quantity_sold', 1),
                    sale_price=sale_data.get('sale_price'),
                    customer=sale_data.get('customer'),
                    sale_date=sale_data['sale_date'],
                    shopify_order_id=sale_data.get('shopify_order_id'),
                    shopify_order_name=sale_data.get('shopify_order_name'),
                    shipping_status=sale_data.get('shipping_status', 'shipped'),
                )

                product.available_quantity = max(0, product.available_quantity - sale.quantity_sold)
                product.save()
                created_sales += 1
            except Exception as e:
                errors.append(f"Sale {i}: {str(e)}")

        return Response({
            'created_lots': created_lots,
            'created_products': created_products,
            'created_sales': created_sales,
            'errors': errors,
        }, status=status.HTTP_201_CREATED if not errors else status.HTTP_207_MULTI_STATUS)

from rest_framework.decorators import action
from rest_framework import viewsets, status
from .models import Sale, ShippingInfo
from .serializers import SaleSerializer, ShippingInfoSerializer
from rest_framework.response import Response
from django.db.models import Sum, F, ExpressionWrapper, DurationField, Count, DateField
from django.utils.timezone import now, make_aware
from datetime import datetime, timedelta
from django_filters import rest_framework as filters
from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from expense.models import Expenses


class SaleFilter(filters.FilterSet):
    start_date = filters.DateFilter(field_name='sale_date', lookup_expr='gte')
    end_date = filters.DateFilter(field_name='sale_date', lookup_expr='lte')
    shipping_status = filters.CharFilter(field_name='shipping_status')
    is_refunded = filters.BooleanFilter(field_name='is_refunded')

    class Meta:
        model = Sale
        fields = ['start_date', 'end_date', 'shipping_status', 'is_refunded']


class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = SaleFilter

    def destroy(self, request, *args, **kwargs):
        """
        Delete a sale and restore the product's available quantity.
        """
        instance = self.get_object()
        product = instance.product
        quantity_sold = instance.quantity_sold
        
        # Restore product quantity
        product.available_quantity += quantity_sold
        product.save()
        
        # Delete the sale
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_date_range(self, duration):
        """Get the start and end dates based on the duration parameter"""
        current_date = now()
        
        if duration == "last_month":
            # Calculate last month
            if current_date.month == 1:
                last_month = 12
                last_month_year = current_date.year - 1
            else:
                last_month = current_date.month - 1
                last_month_year = current_date.year
            
            start_date = make_aware(datetime(last_month_year, last_month, 1))
            if last_month == 12:
                end_date = make_aware(datetime(last_month_year + 1, 1, 1)) - timedelta(days=1)
            else:
                end_date = make_aware(datetime(last_month_year, last_month + 1, 1)) - timedelta(days=1)
                
        elif duration == "current_year":
            # Current year from January 1st to current date
            start_date = make_aware(datetime(current_date.year, 1, 1))
            end_date = current_date
            
        else:  # "current_month" (default)
            # Current month from 1st to current date
            start_date = make_aware(datetime(current_date.year, current_date.month, 1))
            end_date = current_date
        
        return start_date, end_date

    def parse_custom_date(self, date_str):
        """Parse a date string in YYYY-MM-DD format"""
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
            return make_aware(parsed_date)
        except (ValueError, TypeError):
            return None

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

    @extend_schema(
        summary="Get daily sales data",
        description="Returns daily sales data for the specified date range. Use custom start_date/end_date or preset duration.",
        parameters=[
            OpenApiParameter(
                name='start_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Custom start date (YYYY-MM-DD). Takes priority over duration.',
                required=False,
            ),
            OpenApiParameter(
                name='end_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Custom end date (YYYY-MM-DD). Takes priority over duration.',
                required=False,
            ),
            OpenApiParameter(
                name='duration',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Preset duration (used if custom dates not provided)',
                required=False,
                enum=['current_month', 'last_month', 'current_year'],
            ),
        ],
    )
    @action(detail=False, methods=["get"])
    def daily_sales(self, request):
        """
        Returns daily sales data based on the duration parameter or custom date range.
        Duration options: current_month, last_month, current_year
        If no dates are provided (or invalid), returns all sales data without date filtering.
        """
        # Check for custom date range first
        start_date_param = request.query_params.get('start_date')
        end_date_param = request.query_params.get('end_date')
        
        custom_start = self.parse_custom_date(start_date_param)
        custom_end = self.parse_custom_date(end_date_param)
        
        # Check for duration parameter
        duration = request.query_params.get('duration')
        
        start_date = None
        end_date = None
        
        # If both custom dates are provided and valid, use them
        if custom_start and custom_end:
            if custom_start > custom_end:
                return Response(
                    {"error": "start_date must be before or equal to end_date"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            start_date = custom_start
            end_date = custom_end.replace(hour=23, minute=59, second=59)
            duration = "custom"
        elif duration:
            # Use duration-based logic only if duration is explicitly provided
            valid_durations = ['current_month', 'last_month', 'current_year']
            if duration in valid_durations:
                start_date, end_date = self.get_date_range(duration)
            # If duration is invalid, we'll return all data (start_date and end_date stay None)
        
        # Build base queryset
        sales_queryset = Sale.objects.all()
        
        # Apply date filters only if we have valid dates
        if start_date and end_date:
            sales_queryset = sales_queryset.filter(
                sale_date__gte=start_date,
                sale_date__lte=end_date
            )
        
        # Get sales data grouped by date
        sales_data = sales_queryset.annotate(
            date=ExpressionWrapper(
                F('sale_date__date'),
                output_field=DateField()
            )
        ).values('date').annotate(
            total_sales=Count('id'),
            total_amount=Sum(F('quantity_sold') * F('sale_price'))
        ).order_by('date')

        # If we have date range, create a list of all dates
        if start_date and end_date:
            all_dates = []
            current = start_date.date()
            while current <= end_date.date():
                all_dates.append(current)
                current += timedelta(days=1)

            # Create response data with all dates, including those with no sales
            response_data = []
            for date in all_dates:
                date_str = date.strftime("%Y-%m-%d")
                sales_for_date = next(
                    (item for item in sales_data if item['date'] == date),
                    {'total_sales': 0, 'total_amount': 0}
                )
                response_data.append({
                    "date": date_str,
                    "total_sales": sales_for_date['total_sales'],
                    "total_amount": float(sales_for_date['total_amount'] or 0)
                })
            
            return Response({
                "duration": duration,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "daily_sales": response_data
            })
        else:
            # No date filter - return all sales grouped by date
            response_data = []
            for item in sales_data:
                response_data.append({
                    "date": item['date'].strftime("%Y-%m-%d") if item['date'] else None,
                    "total_sales": item['total_sales'],
                    "total_amount": float(item['total_amount'] or 0)
                })
            
            return Response({
                "duration": "all",
                "start_date": None,
                "end_date": None,
                "daily_sales": response_data
            })

    @action(detail=True, methods=["patch"])
    def update_shipping_status(self, request, pk=None):
        """
        Update the shipping status of a specific sale item.
        """
        try:
            sale = self.get_object()
            new_status = request.data.get('shipping_status')
            
            if not new_status:
                return Response(
                    {"error": "shipping_status is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate the shipping status choice
            valid_statuses = [choice[0] for choice in Sale.ShippingStatus.choices]
            if new_status not in valid_statuses:
                return Response(
                    {"error": f"Invalid shipping status. Valid options are: {', '.join(valid_statuses)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update the shipping status
            sale.shipping_status = new_status
            sale.save()
            
            # Return the updated sale
            serializer = self.get_serializer(sale)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        summary="Mark sale as refund",
        description="Marks a sale as refunded. Restores product quantity and creates a refund expense.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'reason': {'type': 'string', 'description': 'Reason for refund'},
                },
                'example': {'reason': 'Customer returned - product defective'}
            }
        },
        responses={200: {'description': 'Sale marked as refunded successfully'}},
    )
    @action(detail=True, methods=["post"])
    def mark_as_refund(self, request, pk=None):
        """
        Mark a sale as refunded:
        1. Restore product's available_quantity
        2. Create a refund expense entry
        3. Mark the sale as refunded (keeps the record)
        """
        try:
            with transaction.atomic():
                sale = self.get_object()
                
                # Check if already refunded
                if sale.is_refunded:
                    return Response(
                        {"error": "This sale has already been refunded"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                product = sale.product
                quantity_sold = sale.quantity_sold
                refund_amount = sale.sale_price * quantity_sold
                reason = request.data.get('reason', '')
                
                # 1. Restore product quantity
                product.available_quantity += quantity_sold
                product.save()
                
                # 2. Create refund expense (this will offset the sale in cashflow)
                refund_expense = Expenses.objects.create(
                    type=Expenses.ExpenseType.REFUND,
                    amount=refund_amount,
                    date=now().date(),
                    description=f"Refund for Sale #{sale.id} - {product.name}. {reason}".strip(),
                    sale=sale,
                    product=product
                )
                
                # 3. Mark sale as refunded
                sale.is_refunded = True
                sale.refunded_at = now()
                sale.save()
                
                # Return success response
                serializer = self.get_serializer(sale)
                return Response({
                    "message": "Sale marked as refunded successfully",
                    "sale": serializer.data,
                    "refund_expense": {
                        "id": refund_expense.id,
                        "amount": float(refund_expense.amount),
                        "date": refund_expense.date.strftime("%Y-%m-%d"),
                        "description": refund_expense.description
                    },
                    "product_quantity_restored": quantity_sold
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            return Response(
                {"error": f"Failed to process refund: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )




class ShippingInfoViewSet(viewsets.ModelViewSet):
    queryset = ShippingInfo.objects.all()
    serializer_class = ShippingInfoSerializer

    @action(detail=True, methods=["get"])
    def get_shipping_info(self, request, pk=None):
        shipping_info = self.get_object().shipping_info
        if shipping_info:
            serializer = self.get_serializer(shipping_info)
            return Response(serializer.data)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)   

    @action(detail=True, methods=["post"])
    def create_shipping_info(self, request, pk=None):
        sale = self.get_object()
        shipping_info = ShippingInfo.objects.create(
            sale=sale,
            customer_name=request.data.get('customer_name'),
            customer_email=request.data.get('customer_email'),
            customer_phone=request.data.get('customer_phone'),
            customer_address=request.data.get('customer_address'),
            customer_pincode=request.data.get('customer_pincode')
        )
        return Response(status=status.HTTP_201_CREATED)
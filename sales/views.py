from rest_framework.decorators import action
from rest_framework import viewsets, status
from .models import Sale
from .serializers import SaleSerializer
from rest_framework.response import Response
from django.db.models import Sum, F, ExpressionWrapper, DurationField, Count, DateField
from django.utils.timezone import now
from datetime import datetime, timedelta


class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer

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
            
            start_date = datetime(last_month_year, last_month, 1)
            if last_month == 12:
                end_date = datetime(last_month_year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = datetime(last_month_year, last_month + 1, 1) - timedelta(days=1)
                
        elif duration == "current_year":
            # Current year (January 1st to December 31st)
            start_date = datetime(current_date.year, 1, 1)
            end_date = datetime(current_date.year, 12, 31)
            
        else:  # "current_month" (default)
            # Current month
            start_date = datetime(current_date.year, current_date.month, 1)
            if current_date.month == 12:
                end_date = datetime(current_date.year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = datetime(current_date.year, current_date.month + 1, 1) - timedelta(days=1)
        
        return start_date, end_date

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

    @action(detail=False, methods=["get"])
    def daily_sales(self, request):
        """
        Returns daily sales data based on the duration parameter.
        Duration options: current_month (default), last_month, current_year
        """
        # Get duration from request parameters, default to "current_month"
        duration = request.query_params.get('duration', 'current_month')
        
        # Validate duration parameter
        valid_durations = ['current_month', 'last_month', 'current_year']
        if duration not in valid_durations:
            duration = 'current_month'  # Default to current month if invalid
        
        start_date, end_date = self.get_date_range(duration)
        
        # Get all sales from start date to end date
        sales_data = Sale.objects.filter(
            sale_date__gte=start_date,
            sale_date__lte=end_date
        ).annotate(
            date=ExpressionWrapper(
                F('sale_date__date'),
                output_field=DateField()
            )
        ).values('date').annotate(
            total_sales=Count('id'),
            total_amount=Sum(F('quantity_sold') * F('sale_price'))
        ).order_by('date')

        # Create a list of dates from start date to end date
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

        # Add metadata about the duration and date range
        return Response({
            "duration": duration,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
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



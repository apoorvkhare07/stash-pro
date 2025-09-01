from django.utils.timezone import now, make_aware
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, F
from sales.models import Sale
from expense.models import Expenses
from inventory.models import Product


class AnalyticsView(APIView):
    # permission_classes = [IsAuthenticated]  # Optional: Restrict access to logged-in users

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

    def get(self, request):
        # Get duration from request parameters, default to "current_month"
        duration = request.query_params.get('duration', 'current_month')
        
        # Validate duration parameter
        valid_durations = ['current_month', 'last_month', 'current_year']
        if duration not in valid_durations:
            duration = 'current_month'  # Default to current month if invalid
        
        start_date, end_date = self.get_date_range(duration)
        
        # 1. Inventory Bought in the specified duration
        inventory_bought = Product.objects.filter(
            bought_at__gte=start_date,
            bought_at__lte=end_date
        ).aggregate(total_value=Sum(F('stock') * F('price')))['total_value'] or 0

        # 2. Sales in the specified duration
        sales = Sale.objects.filter(
            sale_date__gte=start_date,
            sale_date__lte=end_date
        ).aggregate(total_revenue=Sum(F('quantity_sold') * F('sale_price')))['total_revenue'] or 0

        cogs = Sale.objects.filter(
            sale_date__gte=start_date,
            sale_date__lte=end_date
        ).aggregate(
            total_cogs=Sum(F('quantity_sold') * F('product__price'))
        )['total_cogs'] or 0

        # 3. Total Unsold Inventory (this doesn't change based on duration)
        total_unsold_inventory = Product.objects.filter(available_quantity__gt=0).aggregate(
            total_value=Sum(F('available_quantity') * F('price'))
        )['total_value'] or 0

        # 4. Expenses in the specified duration
        total_expenses = Expenses.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('amount'))['total'] or 0

        # 5. Profit in the specified duration
        profit = sales - cogs

        # Prepare Response Data
        data = {
            "duration": duration,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "inventory_bought": inventory_bought,
            "sales": sales,
            "cost_of_goods_sold": cogs,
            "total_unsold_inventory": total_unsold_inventory,
            "profit": profit,
            "profit_margin": (profit / cogs if cogs else 0) * 100,
            "expenses": total_expenses,
        }

        return Response(data)

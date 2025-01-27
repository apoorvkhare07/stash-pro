from django.utils.timezone import now
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, F
from sales.models import Sale
from expense.models import ShippingExpense, ServicingExpense, MiscellaneousExpense
from inventory.models import Product


class AnalyticsView(APIView):
    # permission_classes = [IsAuthenticated]  # Optional: Restrict access to logged-in users

    def get(self, request):
        current_month = 12
        current_year = now().year - 1

        # 1. Inventory Bought This Month
        inventory_bought_this_month = Product.objects.filter(
            created_at__month=current_month,
            created_at__year=current_year
        ).aggregate(total_value=Sum(F('stock') * F('price')))['total_value'] or 0

        # 2. Sales This Month
        sales_this_month = Sale.objects.filter(
            sale_date__month=current_month,
            sale_date__year=current_year
        ).aggregate(total_revenue=Sum(F('quantity_sold') * F('sale_price')))['total_revenue'] or 0

        cogs_this_month = Sale.objects.filter(
            sale_date__month=current_month,
            sale_date__year=current_year
        ).aggregate(
            total_cogs=Sum(F('quantity_sold') * F('product__price'))
        )['total_cogs'] or 0

        # 3. Total Unsold Inventory
        total_unsold_inventory = Product.objects.filter(available_quantity__gt=0).aggregate(
            total_value=Sum(F('available_quantity') * F('price'))
        )['total_value'] or 0

        # 4. Expenses This Month
        shipping_expenses = ShippingExpense.objects.filter(
            date__month=current_month,
            date__year=current_year
        ).aggregate(total=Sum('cost'))['total'] or 0

        servicing_expenses = ServicingExpense.objects.filter(
            date__month=current_month,
            date__year=current_year
        ).aggregate(total=Sum('cost'))['total'] or 0

        miscellaneous_expenses = MiscellaneousExpense.objects.filter(
            date__month=current_month,
            date__year=current_year
        ).aggregate(total=Sum('cost'))['total'] or 0

        total_expenses = shipping_expenses + servicing_expenses + miscellaneous_expenses

        # 5. Profit This Month
        profit_this_month = sales_this_month - total_expenses

        # Prepare Response Data
        data = {
            "inventory_bought_this_month": inventory_bought_this_month,
            "sales_this_month": sales_this_month,
            "cost_of_goods_sold_this_month": cogs_this_month,
            "total_unsold_inventory": total_unsold_inventory,
            "profit_this_month": profit_this_month,
            "expenses_this_month": {
                "shipping": shipping_expenses,
                "servicing": servicing_expenses,
                "miscellaneous": miscellaneous_expenses,
                "overall": total_expenses,
            },
        }

        return Response(data)

from django.utils.timezone import now, make_aware
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsOwnerGroup
from accounts.mixins import resolve_org
from accounts.models import UserOrganization
from django.db.models import Sum, F, Count, Q, Value, CharField
from django.db.models.functions import TruncMonth, Coalesce
from django.contrib.auth.models import User
from sales.models import Sale
from expense.models import Expenses
from inventory.models import Product, Lot
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes


class AnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerGroup]

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

    @extend_schema(
        summary="Get overall analytics",
        description="Returns analytics data for the specified date range. Use custom start_date/end_date or preset duration.",
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
    def get(self, request):
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
                    status=400
                )
            start_date = custom_start
            # Set end_date to end of day
            end_date = custom_end.replace(hour=23, minute=59, second=59)
            duration = "custom"
        elif duration:
            # Use duration-based logic only if duration is explicitly provided
            valid_durations = ['current_month', 'last_month', 'current_year']
            if duration in valid_durations:
                start_date, end_date = self.get_date_range(duration)
            # If duration is invalid, we'll return all data (start_date and end_date stay None)
        
        # Build querysets with optional date filtering, scoped to org
        org, _ = resolve_org(request)
        inventory_queryset = Product.objects.all()
        sales_queryset = Sale.objects.all()
        expenses_queryset = Expenses.objects.all()
        if org:
            inventory_queryset = inventory_queryset.filter(organization=org)
            sales_queryset = sales_queryset.filter(organization=org)
            expenses_queryset = expenses_queryset.filter(organization=org)
        
        # Apply date filters only if we have valid dates
        if start_date and end_date:
            inventory_queryset = inventory_queryset.filter(
                bought_at__gte=start_date,
                bought_at__lte=end_date
            )
            sales_queryset = sales_queryset.filter(
                sale_date__gte=start_date,
                sale_date__lte=end_date
            )
            expenses_queryset = expenses_queryset.filter(
                date__gte=start_date,
                date__lte=end_date
            )
        
        # 1. Inventory Bought
        inventory_bought = inventory_queryset.aggregate(
            total_value=Sum(F('stock') * F('price'))
        )['total_value'] or 0

        # 2. Sales
        sales = sales_queryset.aggregate(
            total_revenue=Sum(F('quantity_sold') * F('sale_price'))
        )['total_revenue'] or 0

        cogs = sales_queryset.aggregate(
            total_cogs=Sum(F('quantity_sold') * F('product__price'))
        )['total_cogs'] or 0

        # 3. Total Unsold Inventory (this doesn't change based on duration)
        unsold_qs = Product.objects.filter(available_quantity__gt=0)
        if org:
            unsold_qs = unsold_qs.filter(organization=org)
        total_unsold_inventory = unsold_qs.aggregate(
            total_value=Sum(F('available_quantity') * F('price'))
        )['total_value'] or 0

        # 4. Expenses
        total_expenses = expenses_queryset.aggregate(total=Sum('amount'))['total'] or 0

        # 5. Profit
        profit = sales - cogs

        # 6. Top products by revenue (within date range)
        top_products_qs = sales_queryset.values(
            'product__id', 'product__name', 'product__price'
        ).annotate(
            revenue=Sum(F('quantity_sold') * F('sale_price')),
            cogs=Sum(F('quantity_sold') * F('product__price')),
            units_sold=Sum('quantity_sold'),
        ).order_by('-revenue')[:5]

        top_products = [
            {
                'id': p['product__id'],
                'name': p['product__name'],
                'revenue': float(p['revenue'] or 0),
                'cogs': float(p['cogs'] or 0),
                'profit': float((p['revenue'] or 0) - (p['cogs'] or 0)),
                'units_sold': p['units_sold'],
            }
            for p in top_products_qs
        ]

        # Prepare Response Data
        data = {
            "duration": duration if duration else "all",
            "start_date": start_date.strftime("%Y-%m-%d") if start_date else None,
            "end_date": end_date.strftime("%Y-%m-%d") if end_date else None,
            "inventory_bought": inventory_bought,
            "sales": sales,
            "cost_of_goods_sold": cogs,
            "total_unsold_inventory": total_unsold_inventory,
            "profit": profit,
            "profit_margin": (profit / cogs if cogs else 0) * 100,
            "expenses": total_expenses,
            "top_products": top_products,
        }

        return Response(data)


class UserAnalyticsView(APIView):
    """Per-user analytics: who bought how much, monthly, payouts."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org, _ = resolve_org(request)
        if not org:
            return Response({'error': 'No organization selected'}, status=400)

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        # Get all org members
        memberships = UserOrganization.objects.filter(organization=org).select_related('user')

        users_data = []
        for m in memberships:
            user = m.user

            # Lots funded by this user
            lots_qs = Lot.objects.filter(organization=org, funded_by='user', funded_by_user=user)
            sales_qs = Sale.objects.filter(organization=org, funded_by_user=user, is_refunded=False)

            if start_date:
                lots_qs = lots_qs.filter(bought_on__gte=start_date)
                sales_qs = sales_qs.filter(sale_date__date__gte=start_date)
            if end_date:
                lots_qs = lots_qs.filter(bought_on__lte=end_date)
                sales_qs = sales_qs.filter(sale_date__date__lte=end_date)

            lots_total = lots_qs.aggregate(total=Sum('total_price'))['total'] or 0
            lots_count = lots_qs.count()
            products_bought = Product.objects.filter(lot__in=lots_qs).count()

            sales_agg = sales_qs.aggregate(
                total_revenue=Sum(F('quantity_sold') * F('sale_price')),
                total_payout=Sum('user_payout'),
                total_org_revenue=Sum('org_revenue'),
                units_sold=Sum('quantity_sold'),
            )

            # Monthly breakdown
            monthly = sales_qs.annotate(
                month=TruncMonth('sale_date')
            ).values('month').annotate(
                revenue=Sum(F('quantity_sold') * F('sale_price')),
                payout=Sum('user_payout'),
                org_share=Sum('org_revenue'),
                units=Sum('quantity_sold'),
            ).order_by('month')

            users_data.append({
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': m.role,
                'investment': {
                    'lots_count': lots_count,
                    'lots_total': float(lots_total),
                    'products_bought': products_bought,
                },
                'sales': {
                    'total_revenue': float(sales_agg['total_revenue'] or 0),
                    'total_payout': float(sales_agg['total_payout'] or 0),
                    'total_org_revenue': float(sales_agg['total_org_revenue'] or 0),
                    'units_sold': sales_agg['units_sold'] or 0,
                },
                'monthly': [
                    {
                        'month': m['month'].strftime('%Y-%m'),
                        'revenue': float(m['revenue'] or 0),
                        'payout': float(m['payout'] or 0),
                        'org_share': float(m['org_share'] or 0),
                        'units': m['units'] or 0,
                    }
                    for m in monthly
                ],
            })

        return Response(users_data)


class ProductAnalyticsView(APIView):
    """Product analytics: top sellers, aging, categories, listed/unlisted."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org, _ = resolve_org(request)
        if not org:
            return Response({'error': 'No organization selected'}, status=400)

        products = Product.objects.filter(organization=org)
        sales = Sale.objects.filter(organization=org, is_refunded=False)

        # Category breakdown
        by_category = products.values('category').annotate(
            total=Count('id'),
            available=Count('id', filter=Q(available_quantity__gt=0)),
            sold=Count('id', filter=Q(available_quantity=0)),
            total_value=Sum(F('available_quantity') * F('price')),
        ).order_by('-total')

        # Sub-category breakdown
        by_subcategory = products.values('sub_category').annotate(
            total=Count('id'),
            available=Count('id', filter=Q(available_quantity__gt=0)),
            sold=Count('id', filter=Q(available_quantity=0)),
        ).order_by('-total')

        # Top selling products (by units)
        top_sellers = sales.values(
            'product__id', 'product__name', 'product__category', 'product__price'
        ).annotate(
            units_sold=Sum('quantity_sold'),
            revenue=Sum(F('quantity_sold') * F('sale_price')),
        ).order_by('-units_sold')[:10]

        # Aging inventory: available products grouped by age
        today = now().date()
        aging = {
            '0_30': products.filter(available_quantity__gt=0, created_at__date__gte=today - timedelta(days=30)).count(),
            '31_60': products.filter(available_quantity__gt=0, created_at__date__gte=today - timedelta(days=60), created_at__date__lt=today - timedelta(days=30)).count(),
            '61_90': products.filter(available_quantity__gt=0, created_at__date__gte=today - timedelta(days=90), created_at__date__lt=today - timedelta(days=60)).count(),
            '90_plus': products.filter(available_quantity__gt=0, created_at__date__lt=today - timedelta(days=90)).count(),
        }

        # Slow movers: available products older than 60 days with no sales
        slow_movers = products.filter(
            available_quantity__gt=0,
            created_at__date__lt=today - timedelta(days=60),
        ).exclude(
            sales__isnull=False, sales__is_refunded=False
        ).values('id', 'name', 'price', 'category', 'created_at')[:20]

        # Summary
        total_products = products.count()
        available = products.filter(available_quantity__gt=0).count()
        sold = products.filter(available_quantity=0).count()
        total_inventory_value = products.filter(available_quantity__gt=0).aggregate(
            val=Sum(F('available_quantity') * F('price'))
        )['val'] or 0

        # Monthly sales trend by category
        monthly_by_category = sales.annotate(
            month=TruncMonth('sale_date')
        ).values('month', 'product__category').annotate(
            units=Sum('quantity_sold'),
            revenue=Sum(F('quantity_sold') * F('sale_price')),
        ).order_by('month')

        return Response({
            'summary': {
                'total_products': total_products,
                'available': available,
                'sold': sold,
                'inventory_value': float(total_inventory_value),
            },
            'by_category': list(by_category),
            'by_subcategory': list(by_subcategory),
            'top_sellers': list(top_sellers),
            'aging': aging,
            'slow_movers': list(slow_movers),
            'monthly_by_category': list(monthly_by_category),
        })

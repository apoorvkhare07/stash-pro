from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum
from .models import Expenses
from .serializers import ExpensesSerializer
from django_filters import rest_framework as filters
from datetime import datetime
from django.utils.timezone import make_aware, now
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes


class ExpensesFilter(filters.FilterSet):
    type = filters.CharFilter(field_name='type')
    start_date = filters.DateFilter(field_name='date', lookup_expr='gte')
    end_date = filters.DateFilter(field_name='date', lookup_expr='lte')

    class Meta:
        model = Expenses
        fields = ['type', 'start_date', 'end_date']


class ExpensesViewSet(viewsets.ModelViewSet):
    queryset = Expenses.objects.all()
    serializer_class = ExpensesSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = ExpensesFilter

    def get_queryset(self):
        queryset = Expenses.objects.all()
        # Filter by type if provided
        expense_type = self.request.query_params.get('type', None)
        if expense_type:
            queryset = queryset.filter(type=expense_type)
        return queryset.order_by('-date')

    def create(self, request, *args, **kwargs):
        """
        Create a new expense with proper validation and error handling
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Create the expense
            expense = serializer.save()
            
            # Return success response
            headers = self.get_success_headers(serializer.data)
            return Response(
                {
                    "message": f"{expense.type.title()} expense created successfully",
                    "expense": serializer.data
                },
                status=status.HTTP_201_CREATED,
                headers=headers
            )
            
        except Exception as e:
            return Response(
                {"error": f"Failed to create expense: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

    def parse_custom_date(self, date_str):
        """Parse a date string in YYYY-MM-DD format"""
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    @extend_schema(
        summary="Get expense summary",
        description="Returns expense summary by type for the specified date range.",
        parameters=[
            OpenApiParameter(
                name='start_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Start date (YYYY-MM-DD)',
                required=False,
            ),
            OpenApiParameter(
                name='end_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='End date (YYYY-MM-DD)',
                required=False,
            ),
        ],
    )
    @action(detail=False, methods=["get"])
    def summary(self, request):
        """
        Returns expense summary by type, optionally filtered by date range
        """
        # Parse date filters
        start_date = self.parse_custom_date(request.query_params.get('start_date'))
        end_date = self.parse_custom_date(request.query_params.get('end_date'))
        
        # Build base queryset with date filters
        base_queryset = Expenses.objects.all()
        if start_date:
            base_queryset = base_queryset.filter(date__gte=start_date)
        if end_date:
            base_queryset = base_queryset.filter(date__lte=end_date)
        
        summary_data = {}
        for expense_type, display_name in Expenses.ExpenseType.choices:
            filtered = base_queryset.filter(type=expense_type)
            total = filtered.aggregate(total_amount=Sum('amount'))['total_amount'] or 0
            
            summary_data[expense_type] = {
                'display_name': display_name,
                'total_amount': float(total),
                'count': filtered.count()
            }
        
        # Overall total
        overall_total = base_queryset.aggregate(
            total_amount=Sum('amount')
        )['total_amount'] or 0
        
        response_data = {
            'summary_by_type': summary_data,
            'overall_total': float(overall_total),
            'total_count': base_queryset.count()
        }
        
        # Include date range in response if filters were applied
        if start_date or end_date:
            response_data['start_date'] = start_date.strftime("%Y-%m-%d") if start_date else None
            response_data['end_date'] = end_date.strftime("%Y-%m-%d") if end_date else None
        
        return Response(response_data)

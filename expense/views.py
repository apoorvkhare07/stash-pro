from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum
from .models import Expenses
from .serializers import ExpensesSerializer
from django_filters import rest_framework as filters


class ExpensesFilter(filters.FilterSet):
    type = filters.CharFilter(field_name='type')
    date_from = filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = filters.DateFilter(field_name='date', lookup_expr='lte')

    class Meta:
        model = Expenses
        fields = ['type', 'date_from', 'date_to']


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
            
            # Additional validation based on expense type
            expense_type = serializer.validated_data.get('type')
            sale = serializer.validated_data.get('sale')
            product = serializer.validated_data.get('product')
            
            # Custom validation messages
            if expense_type in [Expenses.ExpenseType.REFUND]:
                if not sale:
                    return Response(
                        {"error": f"{expense_type.title()} expenses require a sale association"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if expense_type == Expenses.ExpenseType.SERVICING:
                if not product:
                    return Response(
                        {"error": "Servicing expenses require a product association"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Create the expense
            expense = serializer.save()
            
            # Log the creation (optional)
            print(f"Created {expense_type} expense: {expense.amount} for {expense.description or 'N/A'}")
            
            # Return success response
            headers = self.get_success_headers(serializer.data)
            return Response(
                {
                    "message": f"{expense_type.title()} expense created successfully",
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

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """
        Returns expense summary by type
        """
        summary_data = {}
        for expense_type, display_name in Expenses.ExpenseType.choices:
            total = Expenses.objects.filter(type=expense_type).aggregate(
                total_amount=Sum('amount')
            )['total_amount'] or 0
            
            summary_data[expense_type] = {
                'display_name': display_name,
                'total_amount': float(total),
                'count': Expenses.objects.filter(type=expense_type).count()
            }
        
        # Overall total
        overall_total = Expenses.objects.aggregate(
            total_amount=Sum('amount')
        )['total_amount'] or 0
        
        return Response({
            'summary_by_type': summary_data,
            'overall_total': float(overall_total),
            'total_count': Expenses.objects.count()
        })

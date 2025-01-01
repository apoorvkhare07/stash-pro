from rest_framework import viewsets
from .models import ShippingExpense, ServicingExpense, MiscellaneousExpense
from .serializers import ShippingExpenseSerializer, ServicingExpenseSerializer, MiscellaneousExpenseSerializer

class ShippingExpenseViewSet(viewsets.ModelViewSet):
    queryset = ShippingExpense.objects.all()
    serializer_class = ShippingExpenseSerializer


class ServicingExpenseViewSet(viewsets.ModelViewSet):
    queryset = ServicingExpense.objects.all()
    serializer_class = ServicingExpenseSerializer


class MiscellaneousExpenseViewSet(viewsets.ModelViewSet):
    queryset = MiscellaneousExpense.objects.all()
    serializer_class = MiscellaneousExpenseSerializer

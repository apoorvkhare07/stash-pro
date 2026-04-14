from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, LotViewSet, PaymentViewSet, BulkImportView

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='products')
router.register(r'lots', LotViewSet, basename='lots')
router.register(r'payments', PaymentViewSet, basename='payments')

urlpatterns = [
    path('', include(router.urls)),
    path('bulk-import/', BulkImportView.as_view(), name='bulk_import'),
]
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SaleViewSet
from .views import ShippingInfoViewSet
router = DefaultRouter()
router.register(r'', SaleViewSet)
router.register(r'shipping-info', ShippingInfoViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('unshipped/', include(router.urls)),
]
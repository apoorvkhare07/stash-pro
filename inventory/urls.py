from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, LotViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='products')
router.register(r'lots', LotViewSet, basename='lots')

urlpatterns = [
    path('', include(router.urls)),
    # path('lots/', include(router.urls)),
]
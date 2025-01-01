from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ShippingExpenseViewSet, ServicingExpenseViewSet, MiscellaneousExpenseViewSet

router = DefaultRouter()
router.register(r'shipping', ShippingExpenseViewSet)
router.register(r'servicing', ServicingExpenseViewSet)
router.register(r'miscellaneous', MiscellaneousExpenseViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
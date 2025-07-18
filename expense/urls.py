from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExpensesViewSet

router = DefaultRouter()
router.register(r'', ExpensesViewSet, basename='expenses')

urlpatterns = [
    path('', include(router.urls)),
]
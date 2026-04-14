from django.urls import path
from .views import AnalyticsView, UserAnalyticsView, ProductAnalyticsView

urlpatterns = [
    path('overall/', AnalyticsView.as_view(), name='analytics'),
    path('users/', UserAnalyticsView.as_view(), name='user_analytics'),
    path('products/', ProductAnalyticsView.as_view(), name='product_analytics'),
]

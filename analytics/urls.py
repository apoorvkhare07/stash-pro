from django.urls import path
from .views import AnalyticsView

urlpatterns = [
    path('overall/', AnalyticsView.as_view(), name='analytics'),
]

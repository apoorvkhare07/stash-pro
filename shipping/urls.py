from django.urls import path
from .views import (
    ShopifyOrdersView, CreateShipmentsView, ShipmentStatusView,
    ShopifyOAuthInitView, ShopifyOAuthCallbackView,
)

urlpatterns = [
    path('auth/', ShopifyOAuthInitView.as_view(), name='shopify-oauth-init'),
    path('oauth/callback/', ShopifyOAuthCallbackView.as_view(), name='shopify-oauth-callback'),
    path('orders/', ShopifyOrdersView.as_view(), name='shipping-orders'),
    path('ship/', CreateShipmentsView.as_view(), name='create-shipments'),
    path('status/<str:job_id>/', ShipmentStatusView.as_view(), name='shipment-status'),
]

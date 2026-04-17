from django.urls import path
from .views import (
    ShopifyOrdersView, FulfillOrderView,
    ShopifyOAuthInitView, ShopifyOAuthCallbackView,
    ShopifySyncView, ResolveUnmatchedSaleView,
)

urlpatterns = [
    path('auth/', ShopifyOAuthInitView.as_view(), name='shopify-oauth-init'),
    path('oauth/callback/', ShopifyOAuthCallbackView.as_view(), name='shopify-oauth-callback'),
    path('orders/', ShopifyOrdersView.as_view(), name='shipping-orders'),
    path('fulfill/', FulfillOrderView.as_view(), name='fulfill-order'),
    path('sync/', ShopifySyncView.as_view(), name='shopify-sync'),
    path('resolve-sale/<int:sale_id>/', ResolveUnmatchedSaleView.as_view(), name='resolve-unmatched-sale'),
]

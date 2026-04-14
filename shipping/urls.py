from django.urls import path
from .views import (
    ShopifyOrdersView, FulfillOrderView,
    ShopifyOAuthInitView, ShopifyOAuthCallbackView,
    ShopifyWebhookOrderCreateView, ShopifyWebhookOrderUpdateView,
    ShopifySyncStatusView, ResolveUnmatchedSaleView,
)

urlpatterns = [
    path('auth/', ShopifyOAuthInitView.as_view(), name='shopify-oauth-init'),
    path('oauth/callback/', ShopifyOAuthCallbackView.as_view(), name='shopify-oauth-callback'),
    path('orders/', ShopifyOrdersView.as_view(), name='shipping-orders'),
    path('fulfill/', FulfillOrderView.as_view(), name='fulfill-order'),
    path('webhook/<slug:org_slug>/orders/create/', ShopifyWebhookOrderCreateView.as_view(), name='shopify-webhook-order-create'),
    path('webhook/<slug:org_slug>/orders/update/', ShopifyWebhookOrderUpdateView.as_view(), name='shopify-webhook-order-update'),
    path('sync-status/', ShopifySyncStatusView.as_view(), name='shopify-sync-status'),
    path('resolve-sale/<int:sale_id>/', ResolveUnmatchedSaleView.as_view(), name='resolve-unmatched-sale'),
]

import os
import hmac
import hashlib
import base64
import json
import logging

from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.db import transaction

from sales.models import Sale, ShippingInfo
from inventory.models import Product
from accounts.models import Organization
from .services import get_shopify_orders, fulfill_shopify_order

logger = logging.getLogger(__name__)


class ShopifyOAuthInitView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        store = os.getenv('SHOPIFY_STORE')
        client_id = os.getenv('SHOPIFY_CLIENT_ID')
        redirect_uri = os.getenv('SHOPIFY_REDIRECT_URI', 'http://localhost:8000/api/shipping/oauth/callback/')

        if not store or not client_id:
            return HttpResponse('SHOPIFY_STORE and SHOPIFY_CLIENT_ID must be set in .env', status=400)

        auth_url = (
            f"https://{store}/admin/oauth/authorize"
            f"?client_id={client_id}"
            f"&scope=read_orders,write_orders,write_fulfillments,read_fulfillments"
            f"&redirect_uri={redirect_uri}"
        )
        return HttpResponseRedirect(auth_url)


class ShopifyOAuthCallbackView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        code = request.GET.get('code')
        shop = request.GET.get('shop')

        if not code or not shop:
            return HttpResponse('Missing code or shop parameter', status=400)

        client_id = os.getenv('SHOPIFY_CLIENT_ID')
        client_secret = os.getenv('SHOPIFY_CLIENT_SECRET')

        resp = requests.post(
            f"https://{shop}/admin/oauth/access_token",
            json={'client_id': client_id, 'client_secret': client_secret, 'code': code},
            timeout=15,
        )
        resp.raise_for_status()
        access_token = resp.json().get('access_token')

        return HttpResponse(
            f"<h2>Success!</h2>"
            f"<p>Your access token:</p>"
            f"<pre style='background:#f0f0f0;padding:12px;border-radius:6px'>{access_token}</pre>"
            f"<p>Copy this into your <code>.env</code> as <code>SHOPIFY_ACCESS_TOKEN</code></p>",
            content_type='text/html',
        )


class ShopifyOrdersView(APIView):
    def get(self, request):
        try:
            orders = get_shopify_orders()
            return Response(orders)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FulfillOrderView(APIView):
    def post(self, request):
        sale_id = request.data.get('sale_id')
        shopify_order_id = request.data.get('shopify_order_id')
        tracking_number = request.data.get('tracking_number')

        if not all([sale_id, shopify_order_id, tracking_number]):
            return Response(
                {'error': 'sale_id, shopify_order_id and tracking_number are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update sale shipping status
        try:
            sale = Sale.objects.get(id=sale_id)
            sale.shipping_status = Sale.ShippingStatus.SHIPPING_PLACED
            sale.save()
        except Sale.DoesNotExist:
            return Response({'error': 'Sale not found'}, status=status.HTTP_404_NOT_FOUND)

        # Fulfill on Shopify
        try:
            fulfillment = fulfill_shopify_order(shopify_order_id, tracking_number)
            return Response({
                'success': True,
                'tracking_number': tracking_number,
                'fulfillment_id': fulfillment.get('id'),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def verify_shopify_webhook(request, secret=None):
    """Verify Shopify webhook HMAC signature."""
    if not secret:
        secret = os.getenv('SHOPIFY_WEBHOOK_SECRET', '')
    if not secret:
        return False
    hmac_header = request.META.get('HTTP_X_SHOPIFY_HMAC_SHA256', '')
    digest = hmac.new(
        secret.encode('utf-8'),
        request.body,
        hashlib.sha256
    ).digest()
    computed_hmac = base64.b64encode(digest).decode('utf-8')
    return hmac.compare_digest(computed_hmac, hmac_header)


def resolve_webhook_org(request, org_slug):
    """Resolve org from webhook URL slug. Returns (org, error_response)."""
    try:
        org = Organization.objects.get(slug=org_slug)
    except Organization.DoesNotExist:
        return None, Response({'error': 'Unknown organization'}, status=status.HTTP_404_NOT_FOUND)

    # Verify HMAC with org-specific secret, fallback to env var
    secret = org.shopify_webhook_secret or os.getenv('SHOPIFY_WEBHOOK_SECRET', '')
    if secret and not verify_shopify_webhook(request, secret):
        logger.warning(f"Shopify webhook HMAC verification failed for org {org_slug}")
        return None, Response({'error': 'Invalid signature'}, status=status.HTTP_401_UNAUTHORIZED)

    return org, None


@method_decorator(csrf_exempt, name='dispatch')
class ShopifyWebhookOrderCreateView(APIView):
    """
    Receives Shopify orders/create webhook.
    Auto-creates Sale records and decrements inventory.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, org_slug):
        org, err = resolve_webhook_org(request, org_slug)
        if err:
            return err

        try:
            order = request.data
        except Exception:
            return Response({'error': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)

        shopify_order_id = str(order.get('id', ''))
        order_name = order.get('name', '')

        # Idempotency check
        if Sale.objects.filter(shopify_order_id=shopify_order_id).exists():
            return Response({'status': 'already_processed'}, status=status.HTTP_200_OK)

        line_items = order.get('line_items', [])
        shipping_address = order.get('shipping_address') or {}
        customer_name = f"{shipping_address.get('first_name', '')} {shipping_address.get('last_name', '')}".strip()
        customer_email = order.get('email', '')
        customer_phone = shipping_address.get('phone', '') or order.get('phone', '')

        created_sales = []
        unmatched_items = []

        with transaction.atomic():
            for item in line_items:
                item_name = item.get('title', '')
                item_sku = item.get('sku', '')
                quantity = item.get('quantity', 1)
                price = item.get('price', '0')

                # Match product within this org
                product = None
                org_products = Product.objects.filter(organization=org)
                if item_sku:
                    product = org_products.filter(name__iexact=item_sku).first()
                if not product:
                    product = org_products.filter(name__iexact=item_name).first()
                if not product:
                    product = org_products.filter(name__icontains=item_name).first()

                sale = Sale.objects.create(
                    organization=org,
                    product=product,
                    quantity_sold=quantity,
                    sale_price=price,
                    customer=customer_name or None,
                    sale_date=order.get('created_at'),
                    shopify_order_id=shopify_order_id,
                    shopify_order_name=order_name,
                    shipping_status=Sale.ShippingStatus.SHIPPING_PENDING,
                )

                if product:
                    product.available_quantity = max(0, product.available_quantity - quantity)
                    product.save()
                    created_sales.append(sale.id)
                else:
                    unmatched_items.append({
                        'sale_id': sale.id,
                        'item_name': item_name,
                        'item_sku': item_sku,
                    })
                    logger.warning(f"Unmatched Shopify line item: {item_name} (SKU: {item_sku}) in order {order_name}")

                if shipping_address.get('address1'):
                    address_parts = [
                        shipping_address.get('address1', ''),
                        shipping_address.get('address2', ''),
                        shipping_address.get('city', ''),
                        shipping_address.get('province', ''),
                    ]
                    ShippingInfo.objects.create(
                        sale=sale,
                        customer_name=customer_name,
                        customer_email=customer_email,
                        customer_phone=customer_phone,
                        customer_address=', '.join(p for p in address_parts if p),
                        customer_pincode=shipping_address.get('zip', ''),
                    )

        return Response({
            'status': 'processed',
            'order_name': order_name,
            'sales_created': len(created_sales),
            'unmatched_items': unmatched_items,
        }, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class ShopifyWebhookOrderUpdateView(APIView):
    """Receives Shopify orders/updated webhook for status changes."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, org_slug):
        org, err = resolve_webhook_org(request, org_slug)
        if err:
            return err

        order = request.data
        shopify_order_id = str(order.get('id', ''))

        sales = Sale.objects.filter(shopify_order_id=shopify_order_id, organization=org)
        if not sales.exists():
            return Response({'status': 'no_matching_sales'}, status=status.HTTP_200_OK)

        if order.get('cancelled_at'):
            with transaction.atomic():
                for sale in sales:
                    if not sale.is_refunded and sale.product:
                        sale.product.available_quantity += sale.quantity_sold
                        sale.product.save()
                    sale.is_refunded = True
                    sale.refunded_at = order['cancelled_at']
                    sale.save()
            return Response({'status': 'cancelled', 'sales_updated': sales.count()})

        fulfillment_status = order.get('fulfillment_status', '')
        if fulfillment_status == 'fulfilled':
            tracking = ''
            fulfillments = order.get('fulfillments', [])
            if fulfillments:
                tracking = fulfillments[0].get('tracking_number', '')
            sales.update(
                shipping_status=Sale.ShippingStatus.SHIPPED,
                tracking_number=tracking,
            )

        return Response({'status': 'updated'}, status=status.HTTP_200_OK)


class ShopifySyncStatusView(APIView):
    """Returns Shopify sync status - last synced order, unmatched items."""

    def get(self, request):
        org = getattr(request, 'organization', None)
        qs = Sale.objects.filter(shopify_order_id__isnull=False)
        if org:
            qs = qs.filter(organization=org)

        last_synced = qs.order_by('-created_at').first()

        unmatched_sales = qs.filter(product__isnull=True).values(
            'id', 'shopify_order_name', 'customer', 'sale_price', 'sale_date'
        )

        return Response({
            'last_synced_at': last_synced.created_at if last_synced else None,
            'last_order_name': last_synced.shopify_order_name if last_synced else None,
            'unmatched_count': unmatched_sales.count(),
            'unmatched_sales': list(unmatched_sales),
        })


class ResolveUnmatchedSaleView(APIView):
    """Manually match an unmatched sale to a product."""

    def post(self, request, sale_id):
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({'error': 'product_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            sale = Sale.objects.get(id=sale_id, product__isnull=True)
        except Sale.DoesNotExist:
            return Response({'error': 'Unmatched sale not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            sale.product = product
            sale.save()
            product.available_quantity = max(0, product.available_quantity - sale.quantity_sold)
            product.save()

        return Response({'status': 'matched', 'sale_id': sale.id, 'product_id': product.id})

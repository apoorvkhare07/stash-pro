import os
import logging

from django.http import HttpResponse, HttpResponseRedirect
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.db import transaction

from sales.models import Sale, ShippingInfo
from inventory.models import Product
from accounts.mixins import resolve_org
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

        try:
            sale = Sale.objects.get(id=sale_id)
            sale.shipping_status = Sale.ShippingStatus.SHIPPING_PLACED
            sale.save()
        except Sale.DoesNotExist:
            return Response({'error': 'Sale not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            fulfillment = fulfill_shopify_order(shopify_order_id, tracking_number)
            return Response({
                'success': True,
                'tracking_number': tracking_number,
                'fulfillment_id': fulfillment.get('id'),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ShopifySyncView(APIView):
    """
    Pull-based Shopify sync.
    GET: Fetch Shopify orders not yet in StashPro, with suggested product matches.
    POST: Confirm mappings and create Sale records.
    """

    def get(self, request):
        """Fetch new Shopify orders and suggest product matches."""
        org, _ = resolve_org(request)
        if not org:
            return Response({'error': 'No organization selected'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            shopify_orders = get_shopify_orders()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Find which orders are already synced
        existing_order_ids = set(
            Sale.objects.filter(organization=org, shopify_order_id__isnull=False)
            .values_list('shopify_order_id', flat=True)
        )

        org_products = Product.objects.filter(organization=org, available_quantity__gt=0)

        pending_orders = []
        for order in shopify_orders:
            order_id = str(order['id'])
            if order_id in existing_order_ids:
                continue

            # Try to match each line item to a product
            items_with_matches = []
            for item in order.get('items', []):
                item_name = item.get('name', '')
                suggested_product = None
                suggestions = []

                # Exact match
                exact = org_products.filter(name__iexact=item_name).first()
                if exact:
                    suggested_product = {'id': exact.id, 'name': exact.name, 'price': float(exact.price)}

                # Fuzzy matches for suggestions
                fuzzy = org_products.filter(name__icontains=item_name.split(' ')[0])[:5]
                suggestions = [{'id': p.id, 'name': p.name, 'price': float(p.price)} for p in fuzzy]

                items_with_matches.append({
                    'shopify_item_name': item_name,
                    'quantity': item.get('quantity', 1),
                    'suggested_product': suggested_product,
                    'suggestions': suggestions,
                })

            pending_orders.append({
                'shopify_order_id': order_id,
                'order_name': order['name'],
                'created_at': order['created_at'],
                'customer_name': order['customer_name'],
                'total_price': order['total_price'],
                'items': items_with_matches,
            })

        # Also return sync status
        last_synced = Sale.objects.filter(
            organization=org, shopify_order_id__isnull=False
        ).order_by('-created_at').first()

        unmatched = Sale.objects.filter(
            organization=org, shopify_order_id__isnull=False, product__isnull=True
        ).values('id', 'shopify_order_name', 'customer', 'sale_price', 'sale_date')

        return Response({
            'pending_orders': pending_orders,
            'pending_count': len(pending_orders),
            'last_synced_at': last_synced.created_at if last_synced else None,
            'last_order_name': last_synced.shopify_order_name if last_synced else None,
            'unmatched_count': unmatched.count(),
            'unmatched_sales': list(unmatched),
        })

    def post(self, request):
        """
        Confirm product mappings and create sales.
        Expected body:
        {
            "orders": [
                {
                    "shopify_order_id": "123",
                    "order_name": "#1001",
                    "customer": "john@example.com",
                    "sale_date": "2026-04-01T12:00:00",
                    "items": [
                        {
                            "product_id": 45,       // mapped product (null if skipping)
                            "sale_price": 5000,
                            "quantity": 1
                        }
                    ]
                }
            ]
        }
        """
        org, _ = resolve_org(request)
        if not org:
            return Response({'error': 'No organization selected'}, status=status.HTTP_400_BAD_REQUEST)

        orders_data = request.data.get('orders', [])
        created_sales = 0
        skipped = 0
        errors = []

        for order in orders_data:
            shopify_order_id = str(order.get('shopify_order_id', ''))
            order_name = order.get('order_name', '')

            # Idempotency
            if Sale.objects.filter(shopify_order_id=shopify_order_id).exists():
                skipped += 1
                continue

            items = order.get('items', [])
            for i, item in enumerate(items):
                product_id = item.get('product_id')
                sale_price = item.get('sale_price', 0)
                quantity = item.get('quantity', 1)

                product = None
                if product_id:
                    try:
                        product = Product.objects.get(id=product_id, organization=org)
                    except Product.DoesNotExist:
                        errors.append(f"Product {product_id} not found for order {order_name}")
                        continue

                # Unique order ID for multi-item orders
                unique_id = shopify_order_id if i == 0 else f"{shopify_order_id}-{i+1}"

                try:
                    with transaction.atomic():
                        # Determine funded_by_user from product's lot
                        funded_by_user = None
                        if product and product.lot and product.lot.funded_by == 'user':
                            funded_by_user = product.lot.funded_by_user

                        sale = Sale.objects.create(
                            organization=org,
                            product=product,
                            quantity_sold=quantity,
                            sale_price=sale_price,
                            customer=order.get('customer', ''),
                            sale_date=order.get('sale_date'),
                            shopify_order_id=unique_id,
                            shopify_order_name=order_name,
                            shipping_status=Sale.ShippingStatus.SHIPPING_PENDING,
                            funded_by_user=funded_by_user,
                            cost_price=product.price if product else None,
                        )
                        sale.calculate_split()
                        sale.save()

                        if product:
                            product.available_quantity = max(0, product.available_quantity - quantity)
                            product.save()

                        # Create shipping info if available
                        customer_name = order.get('customer_name', '')
                        address = order.get('address', '')
                        if customer_name:
                            ShippingInfo.objects.create(
                                sale=sale,
                                customer_name=customer_name,
                                customer_email=order.get('customer', ''),
                                customer_phone=order.get('phone', ''),
                                customer_address=address,
                                customer_pincode=order.get('pincode', ''),
                            )

                        created_sales += 1
                except Exception as e:
                    errors.append(f"Order {order_name} item {i}: {str(e)}")

        return Response({
            'created_sales': created_sales,
            'skipped': skipped,
            'errors': errors,
        }, status=status.HTTP_201_CREATED if created_sales > 0 else status.HTTP_200_OK)


class ResolveUnmatchedSaleView(APIView):
    """Manually match an unmatched sale to a product."""

    def post(self, request, sale_id):
        org, _ = resolve_org(request)
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({'error': 'product_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            sale = Sale.objects.get(id=sale_id, product__isnull=True, organization=org)
        except Sale.DoesNotExist:
            return Response({'error': 'Unmatched sale not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            product = Product.objects.get(id=product_id, organization=org)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            sale.product = product
            sale.funded_by_user = product.lot.funded_by_user if product.lot and product.lot.funded_by == 'user' else None
            sale.cost_price = product.price
            sale.calculate_split()
            sale.save()
            product.available_quantity = max(0, product.available_quantity - sale.quantity_sold)
            product.save()

        return Response({'status': 'matched', 'sale_id': sale.id, 'product_id': product.id})

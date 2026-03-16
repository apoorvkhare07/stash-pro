import os
from django.http import HttpResponse, HttpResponseRedirect
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from sales.models import Sale
from .services import get_shopify_orders, fulfill_shopify_order


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

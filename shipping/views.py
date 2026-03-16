import os
import threading
import requests
from django.http import HttpResponse, HttpResponseRedirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from .services import get_shopify_orders, create_job, get_job, run_shipping_job


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
            f"&scope=read_orders,write_orders"
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

        print(f"\n{'='*60}")
        print(f"SHOPIFY ACCESS TOKEN: {access_token}")
        print(f"Add this to your .env:")
        print(f"SHOPIFY_ACCESS_TOKEN={access_token}")
        print(f"{'='*60}\n")

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


class CreateShipmentsView(APIView):
    def post(self, request):
        orders = request.data.get('orders', [])
        if not orders:
            return Response({'error': 'No orders provided'}, status=status.HTTP_400_BAD_REQUEST)

        job_id = create_job([o['id'] for o in orders])
        thread = threading.Thread(target=run_shipping_job, args=(job_id, orders), daemon=True)
        thread.start()

        return Response({'job_id': job_id}, status=status.HTTP_202_ACCEPTED)


class ShipmentStatusView(APIView):
    def get(self, request, job_id):
        job = get_job(job_id)
        if not job:
            return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(job)

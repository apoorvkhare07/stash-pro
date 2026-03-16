import os
import requests


def _shopify_headers():
    return {'X-Shopify-Access-Token': os.getenv('SHOPIFY_ACCESS_TOKEN', '')}


def _shopify_url(path):
    store = os.getenv('SHOPIFY_STORE')
    return f"https://{store}/admin/api/2024-01/{path}"


# ---- Shopify Orders ----

def get_shopify_orders():
    store = os.getenv('SHOPIFY_STORE')
    token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    if not store or not token:
        raise ValueError("SHOPIFY_STORE and SHOPIFY_ACCESS_TOKEN must be set in .env")

    response = requests.get(
        _shopify_url('orders.json'),
        params={'status': 'open', 'fulfillment_status': 'unfulfilled', 'limit': 250},
        headers=_shopify_headers(),
        timeout=30,
    )
    response.raise_for_status()
    orders = response.json().get('orders', [])
    return [_clean_order(o) for o in orders]


def _clean_order(order):
    shipping = order.get('shipping_address') or {}
    line_items = order.get('line_items', [])
    is_cod = order.get('payment_gateway', '').lower() in ('cash_on_delivery', 'cod', 'manual')
    return {
        'id': order['id'],
        'name': order['name'],
        'created_at': order.get('created_at', ''),
        'customer_name': f"{shipping.get('first_name', '')} {shipping.get('last_name', '')}".strip(),
        'phone': shipping.get('phone') or order.get('phone') or '',
        'address1': shipping.get('address1', ''),
        'address2': shipping.get('address2', ''),
        'city': shipping.get('city', ''),
        'province': shipping.get('province', ''),
        'zip': shipping.get('zip', ''),
        'country': shipping.get('country', ''),
        'total_price': order.get('total_price', '0.00'),
        'items': [{'name': i['name'], 'quantity': i['quantity']} for i in line_items],
        'payment_gateway': order.get('payment_gateway', ''),
        'financial_status': order.get('financial_status', ''),
        'is_cod': is_cod,
    }


# ---- Shopify Fulfillment ----

def fulfill_shopify_order(shopify_order_id, tracking_number, tracking_company='Delhivery'):
    # Step 1: get fulfillment order ID
    resp = requests.get(
        _shopify_url(f'orders/{shopify_order_id}/fulfillment_orders.json'),
        headers=_shopify_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    fulfillment_orders = resp.json().get('fulfillment_orders', [])
    if not fulfillment_orders:
        raise ValueError("No fulfillment orders found for this Shopify order")

    fo_id = fulfillment_orders[0]['id']

    # Step 2: create fulfillment with tracking
    payload = {
        'fulfillment': {
            'line_items_by_fulfillment_order': [{'fulfillment_order_id': fo_id}],
            'tracking_info': {
                'number': tracking_number,
                'company': tracking_company,
            },
            'notify_customer': True,
        }
    }
    resp = requests.post(
        _shopify_url('fulfillments.json'),
        json=payload,
        headers=_shopify_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get('fulfillment', {})

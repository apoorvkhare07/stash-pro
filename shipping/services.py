import os
import uuid
import threading
import requests


# ---- Job management ----

_jobs = {}
_jobs_lock = threading.Lock()


def create_job(order_ids):
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            'status': 'pending',
            'total': len(order_ids),
            'processed': 0,
            'results': {},
            'error': None,
        }
    return job_id


def get_job(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def _update_job(job_id, **kwargs):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


# ---- Shopify ----

def get_shopify_orders():
    store = os.getenv('SHOPIFY_STORE')
    token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    if not store or not token:
        raise ValueError("SHOPIFY_STORE and SHOPIFY_ACCESS_TOKEN must be set in .env")

    url = f"https://{store}/admin/api/2024-01/orders.json"
    params = {
        'status': 'open',
        'fulfillment_status': 'unfulfilled',
        'limit': 250,
    }
    headers = {'X-Shopify-Access-Token': token}
    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()

    orders = response.json().get('orders', [])
    return [_clean_order(o) for o in orders]


def _clean_order(order):
    shipping = order.get('shipping_address') or {}
    line_items = order.get('line_items', [])
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
    }


# ---- Delhivery Automation ----

class ShippingAutomation:
    DELHIVERY_URL = 'https://www.delhivery.com/b2c/'

    def __init__(self, job_id, orders):
        self.job_id = job_id
        self.orders = orders
        self._page = None

    def start(self):
        from playwright.sync_api import sync_playwright

        _update_job(self.job_id, status='running')

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, slow_mo=100)
            context = browser.new_context()
            self._page = context.new_page()

            try:
                self._login()
                for i, order in enumerate(self.orders):
                    try:
                        awb = self._process_order(order)
                        with _jobs_lock:
                            _jobs[self.job_id]['results'][str(order['id'])] = {
                                'success': True,
                                'awb': awb,
                                'order_name': order['name'],
                            }
                    except Exception as e:
                        with _jobs_lock:
                            _jobs[self.job_id]['results'][str(order['id'])] = {
                                'success': False,
                                'error': str(e),
                                'order_name': order['name'],
                            }
                    with _jobs_lock:
                        _jobs[self.job_id]['processed'] = i + 1

                _update_job(self.job_id, status='completed')
            except Exception as e:
                _update_job(self.job_id, status='failed', error=str(e))
            finally:
                context.close()
                browser.close()

    def _login(self):
        email = os.getenv('DELHIVERY_EMAIL')
        password = os.getenv('DELHIVERY_PASSWORD')
        if not email or not password:
            raise ValueError("DELHIVERY_EMAIL and DELHIVERY_PASSWORD must be set in .env")

        self._page.goto(self.DELHIVERY_URL)
        self._page.wait_for_load_state('networkidle', timeout=15000)

        self._fill_field('input[type="email"], input[name="email"], input[placeholder*="email" i]', email)
        self._fill_field('input[type="password"]', password)
        self._page.click('button[type="submit"]')
        self._page.wait_for_load_state('networkidle', timeout=15000)

    def _process_order(self, order):
        self._page.goto(f"{self.DELHIVERY_URL}consignment/create/")
        self._page.wait_for_load_state('networkidle', timeout=15000)

        # Consignee details
        self._fill_field('input[name="name"], input[placeholder*="name" i]', order['customer_name'])
        self._fill_field('input[name="phone"], input[placeholder*="phone" i]', order['phone'])
        self._fill_field('input[name="address"], input[placeholder*="address" i]', order['address1'])
        self._fill_field('input[name="pin"], input[placeholder*="pin" i], input[placeholder*="pincode" i]', order['zip'])
        self._fill_field('input[name="city"], input[placeholder*="city" i]', order['city'])
        self._fill_field('input[name="state"], input[placeholder*="state" i]', order['province'])

        # Order details
        item_summary = ', '.join(f"{i['name']} x{i['quantity']}" for i in order['items'])
        is_cod = order.get('payment_gateway', '').lower() in ('cash_on_delivery', 'cod')
        cod_amount = str(order['total_price']) if is_cod else '0'

        self._fill_field('input[name="order_id"], input[placeholder*="order" i]', order['name'])
        self._fill_field('textarea[name="comments"], input[name="comments"]', item_summary)
        self._fill_field('input[name="cod_amount"], input[placeholder*="cod" i]', cod_amount)

        # Submit
        self._page.click('button[type="submit"]')
        self._page.wait_for_load_state('networkidle', timeout=15000)

        return self._extract_awb()

    def _fill_field(self, selector, value):
        try:
            locator = self._page.locator(selector).first
            locator.wait_for(state='visible', timeout=5000)
            locator.fill(str(value))
        except Exception:
            pass

    def _extract_awb(self):
        try:
            awb_locator = self._page.locator(
                '[class*="awb"], [class*="waybill"], [data-testid*="awb"], '
                '[class*="tracking"], text=/\\b\\d{10,18}\\b/'
            ).first
            awb_locator.wait_for(state='visible', timeout=8000)
            return awb_locator.inner_text().strip()
        except Exception:
            return None


def run_shipping_job(job_id, orders):
    automation = ShippingAutomation(job_id, orders)
    automation.start()

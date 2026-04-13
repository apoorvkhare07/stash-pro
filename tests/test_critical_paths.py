"""
Critical-path tests for StashPro Django backend.

Run with:
    SECRET_KEY=test-secret python manage.py test tests.test_critical_paths --settings=tests.test_settings
"""
import datetime
from decimal import Decimal

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils.timezone import now
from rest_framework.test import APIClient
from rest_framework import status

from inventory.models import Product, Lot, Payment
from sales.models import Sale
from expense.models import Expenses


# ---------------------------------------------------------------------------
# 1. Auth tests
# ---------------------------------------------------------------------------
class AuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_login_valid_credentials(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "testuser", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_login_invalid_credentials(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "testuser", "password": "wrongpass"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh(self):
        login = self.client.post(
            "/api/auth/login/",
            {"username": "testuser", "password": "testpass123"},
            format="json",
        )
        refresh_token = login.data["refresh"]
        resp = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)

    def test_protected_endpoint_requires_token(self):
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Helper mixin – creates a logged-in client + common test data
# ---------------------------------------------------------------------------
class AuthenticatedTestMixin:
    """Mixin that provides an authenticated API client and common test objects."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        login = self.client.post(
            "/api/auth/login/",
            {"username": "testuser", "password": "testpass123"},
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}"
        )

        # Common objects
        self.lot = Lot.objects.create(
            title="Test Lot",
            total_price=Decimal("10000.00"),
            bought_on=datetime.date.today(),
        )
        self.product = Product.objects.create(
            name="Canon AE-1",
            price=Decimal("5000.00"),
            stock=5,
            available_quantity=5,
            category=Product.Category.FILM_CAMERA,
            lot=self.lot,
        )


# ---------------------------------------------------------------------------
# 2. Sale creation tests
# ---------------------------------------------------------------------------
class SaleCreationTests(AuthenticatedTestMixin, TestCase):
    def test_sale_decrements_available_quantity(self):
        resp = self.client.post(
            "/api/sales/",
            {
                "product": self.product.id,
                "quantity_sold": 2,
                "sale_price": "6000.00",
                "sale_date": now().isoformat(),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.product.refresh_from_db()
        self.assertEqual(self.product.available_quantity, 3)

    def test_sale_exceeding_quantity_fails(self):
        resp = self.client.post(
            "/api/sales/",
            {
                "product": self.product.id,
                "quantity_sold": 10,
                "sale_price": "6000.00",
                "sale_date": now().isoformat(),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sale_creation_returns_proper_data(self):
        resp = self.client.post(
            "/api/sales/",
            {
                "product": self.product.id,
                "quantity_sold": 1,
                "sale_price": "6000.00",
                "sale_date": now().isoformat(),
                "customer": "Test Customer",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["quantity_sold"], 1)
        self.assertEqual(Decimal(resp.data["sale_price"]), Decimal("6000.00"))
        self.assertEqual(resp.data["customer"], "Test Customer")
        self.assertIn("id", resp.data)
        self.assertIn("product_details", resp.data)


# ---------------------------------------------------------------------------
# 3. Refund tests
# ---------------------------------------------------------------------------
class RefundTests(AuthenticatedTestMixin, TestCase):
    def _create_sale(self, quantity=1, price="5000.00"):
        sale = Sale.objects.create(
            product=self.product,
            quantity_sold=quantity,
            sale_price=Decimal(price),
            sale_date=now(),
            shipping_status=Sale.ShippingStatus.SHIPPING_PENDING,
        )
        self.product.available_quantity -= quantity
        self.product.save()
        return sale

    def test_refund_restores_available_quantity(self):
        sale = self._create_sale(quantity=2)
        self.assertEqual(self.product.available_quantity, 3)

        resp = self.client.post(
            f"/api/sales/{sale.id}/mark_as_refund/",
            {"reason": "Defective"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.available_quantity, 5)

    def test_refund_already_refunded_fails(self):
        sale = self._create_sale()
        # First refund
        self.client.post(
            f"/api/sales/{sale.id}/mark_as_refund/",
            {"reason": "Defective"},
            format="json",
        )
        # Second refund should fail
        resp = self.client.post(
            f"/api/sales/{sale.id}/mark_as_refund/",
            {"reason": "Duplicate"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", resp.data)

    def test_refund_creates_expense_entry(self):
        sale = self._create_sale(quantity=1, price="5000.00")
        self.client.post(
            f"/api/sales/{sale.id}/mark_as_refund/",
            {"reason": "Customer returned"},
            format="json",
        )
        expense = Expenses.objects.filter(
            type=Expenses.ExpenseType.REFUND, sale=sale
        ).first()
        self.assertIsNotNone(expense)
        self.assertEqual(expense.amount, Decimal("5000.00"))
        self.assertEqual(expense.product, self.product)


# ---------------------------------------------------------------------------
# 4. Stock management tests
# ---------------------------------------------------------------------------
class StockManagementTests(AuthenticatedTestMixin, TestCase):
    def test_product_stock_update_adjusts_available_quantity(self):
        resp = self.client.patch(
            f"/api/inventory/products/{self.product.id}/",
            {"stock": 8},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        # stock went from 5 -> 8, diff = +3, available_quantity = 5 + 3 = 8
        self.assertEqual(self.product.available_quantity, 8)

    def test_delete_product_with_sales_fails(self):
        Sale.objects.create(
            product=self.product,
            quantity_sold=1,
            sale_price=Decimal("5000.00"),
            sale_date=now(),
            shipping_status=Sale.ShippingStatus.SHIPPING_PENDING,
        )
        resp = self.client.delete(
            f"/api/inventory/products/{self.product.id}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", resp.data)

    def test_delete_lot_with_products_fails(self):
        resp = self.client.delete(f"/api/inventory/lots/{self.lot.id}/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", resp.data)


# ---------------------------------------------------------------------------
# 5. Payment / Lot status tests
# ---------------------------------------------------------------------------
class PaymentLotStatusTests(AuthenticatedTestMixin, TestCase):
    def test_payment_updates_lot_status_to_partially_paid(self):
        resp = self.client.post(
            "/api/inventory/payments/",
            {
                "lot": self.lot.id,
                "amount": "3000.00",
                "payment_date": datetime.date.today().isoformat(),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.status, Lot.PaymentStatus.PARTIALLY_PAID)

    def test_payment_totaling_lot_price_sets_paid(self):
        Payment.objects.create(
            lot=self.lot,
            amount=Decimal("7000.00"),
            payment_date=datetime.date.today(),
        )
        # Create second payment via API to total 10000
        resp = self.client.post(
            "/api/inventory/payments/",
            {
                "lot": self.lot.id,
                "amount": "3000.00",
                "payment_date": datetime.date.today().isoformat(),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.status, Lot.PaymentStatus.PAID)

    def test_deleting_payment_recalculates_lot_status(self):
        payment = Payment.objects.create(
            lot=self.lot,
            amount=Decimal("10000.00"),
            payment_date=datetime.date.today(),
        )
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.status, Lot.PaymentStatus.PAID)

        resp = self.client.delete(
            f"/api/inventory/payments/{payment.id}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.status, Lot.PaymentStatus.PAYMENT_PENDING)

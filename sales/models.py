from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

from inventory.models import Product
from inventory.models import BaseModel
from accounts.models import Organization


class Sale(BaseModel):

    class ShippingStatus(models.TextChoices):
        SHIPPING_PENDING = "shipping_pending", _("Shipping Pending")
        SHIPPING_PLACED = "shipping_placed", _("Shipping Placed")
        SHIPPED = "shipped", _("Shipped")

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='sales', null=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="sales", null=True, blank=True)
    quantity_sold = models.PositiveIntegerField()
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)
    customer = models.CharField(max_length=255, null=True, blank=True)
    shipping_status = models.CharField(
        max_length=128,
        choices=ShippingStatus.choices,
        null=True,
        blank=True
    )
    sale_date = models.DateTimeField()
    shopify_order_id = models.CharField(max_length=64, null=True, blank=True, unique=True)
    shopify_order_name = models.CharField(max_length=64, null=True, blank=True)
    tracking_number = models.CharField(max_length=128, null=True, blank=True)
    is_refunded = models.BooleanField(default=False)
    refunded_at = models.DateTimeField(null=True, blank=True)

    # Revenue split fields
    funded_by_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='funded_sales')
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    user_payout = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    org_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def calculate_split(self):
        """Calculate revenue split based on funding source."""
        total = self.sale_price * self.quantity_sold
        cp = self.cost_price or (self.product.price if self.product else 0)
        self.cost_price = cp

        if self.funded_by_user:
            # User-funded: user gets cost price back, org gets margin
            self.user_payout = cp * self.quantity_sold
            self.org_revenue = total - self.user_payout
        else:
            # Org-funded: org gets everything
            self.user_payout = 0
            self.org_revenue = total

    def __str__(self):
        product_name = self.product.name if self.product else 'Unmatched'
        return f"Sale of {product_name} on {self.sale_date}"



class ShippingInfo(BaseModel):
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=255)
    customer_address = models.TextField()
    customer_pincode = models.CharField(max_length=255)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="shipping_info")
from django.db import models
from django.utils.translation import gettext_lazy as _

from inventory.models import Product
from inventory.models import BaseModel


class Sale(BaseModel):

    class ShippingStatus(models.TextChoices):
        SHIPPING_PENDING = "shipping_pending", _("Shipping Pending")
        SHIPPING_PLACED = "shipping_placed", _("Shipping Placed")
        SHIPPED = "shipped", _("Shipped")

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="sales")
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

    def __str__(self):
        return f"Sale of {self.product.name} on {self.sale_date}"



class ShippingInfo(BaseModel):
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=255)
    customer_address = models.TextField()
    customer_pincode = models.CharField(max_length=255)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="shipping_info")
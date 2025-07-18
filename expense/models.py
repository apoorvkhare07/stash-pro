from django.db import models
from django.utils.translation import gettext_lazy as _
from inventory.models import Product
from sales.models import Sale
from inventory.models import BaseModel


class Expenses(BaseModel):
    class ExpenseType(models.TextChoices):
        SERVICING = "servicing", _("Servicing")
        REFUND = "refund", _("Refund")
        SHIPPING = "shipping", _("Shipping")
        MISC = "misc", _("Miscellaneous")

    type = models.CharField(
        max_length=50,
        choices=ExpenseType.choices
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(null=True, blank=True)
    vendor = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateField(auto_now_add=True)
    
    # Optional relationships - depending on expense type
    sale = models.ForeignKey(
        Sale, 
        on_delete=models.CASCADE, 
        related_name="expenses", 
        null=True, 
        blank=True
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name="expenses", 
        null=True, 
        blank=True
    )

    def __str__(self):
        if self.type == self.ExpenseType.SHIPPING and self.sale:
            return f"Shipping for Sale ID {self.sale.id} - {self.amount}"
        elif self.type == self.ExpenseType.SERVICING and self.product:
            return f"Servicing for Product {self.product.name} - {self.amount}"
        elif self.type == self.ExpenseType.REFUND and self.sale:
            return f"Refund for Sale ID {self.sale.id} - {self.amount}"
        else:
            return f"{self.get_type_display()} Expense - {self.amount}"

    class Meta:
        verbose_name = "Expense"
        verbose_name_plural = "Expenses"


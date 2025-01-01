from django.db import models
from inventory.models import Product
from sales.models import Sale
from inventory.models import BaseModel

class ShippingExpense(BaseModel):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="shipping_expenses")
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(null=True, blank=True)
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Shipping for Sale ID {self.sale.id} - {self.cost}"


class ServicingExpense(BaseModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="servicing_expenses")
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(null=True, blank=True)
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Servicing for Product {self.product.name} - {self.cost}"


class MiscellaneousExpense(BaseModel):
    description = models.TextField()
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Miscellaneous Expense - {self.cost}"


from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _


class BaseModel(models.Model):
    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Product(BaseModel):

    class Category(models.TextChoices):
        FILM_CAMERA = "Film Camera", _("Film Camera")
        DIGIRAL_CAMERA = "Digital Camera", _("Digital Camera")
        ACCESSORY = "Accessory", _("Accessory")
        FILM = "Film", _("Film")

    class SubCategory(models.TextChoices):
        SLR = "SLR", _("SLR")
        POINT_AND_SHOOT = "Point & Shoot", _("Point & Shoot")
        MIRRORLESS = "Mirrorless", _("Mirrorless")
        TRIPOD = "Tripod", _("Tripod")
        LENS = "Lens", _("Lens")
        FILM_ROLL = "Film Roll", _("Film Roll")
        RANGEFINDER = "Rangefinder", _("Rangefinder")
        TLR = "TLR", _("TLR")
        HANDYCAM = "Handycam", _("Handycam")

    class CosmeticCondition(models.TextChoices):
        EXCELLENT = "excellent", _("Excellent")
        VERY_GOOD = "very_good", _("Very Good")
        GOOD = "good", _("Good")
        AVERAGE = "average", _("Average")
        BELOW_AVERAGE = "below_average", _("Below Average")

    class WorkingCondition(models.TextChoices):
        FULLY_WORKING = "fully_working", _("Fully Working")
        PARTIALLY_WORKING = "partially_working", _("Partially Working")
        NEEDS_SERVICE = "needs_service", _("Needs Service")
        NON_WORKING = "non_working", _("Non Working")

    class DeliveryStatus(models.TextChoices):
        RECEIVED = "received", _("Received")
        NEEDS_SERVICE = "needs_service", _("Needs Service")
        SENT_FOR_SERVICE = "sent_for_service", _("Sent For Service")

    name = models.CharField(max_length=255)
    specs = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=1)
    available_quantity = models.PositiveIntegerField(default=1)
    category = models.CharField(
        max_length=50,
        choices=Category.choices,
        null=True,
        blank=True
    )
    sub_category = models.CharField(
        max_length=50,
        choices=SubCategory.choices,
        null=True,
        blank=True
    )
    cosmetic_condition = models.CharField(
        max_length=50,
        choices=CosmeticCondition.choices,
        null=True,
        blank=True
    )
    working_condition = models.CharField(
        max_length=50,
        choices=WorkingCondition.choices,
        null=True,
        blank=True
    )
    delivery_status = models.CharField(
        max_length=50,
        choices=DeliveryStatus.choices,
        null=True,
        blank=True
    )
    overall_condition = models.CharField(max_length=512, null=True, blank=True)
    bought_from = models.CharField(max_length=255, null=True, blank=True)
    bought_at = models.DateTimeField(null=True, blank=True)
    lot = models.ForeignKey('Lot', on_delete=models.SET_NULL, null=True, blank=True, related_name='products')

    def __str__(self):
        return f"{self.name} ({self.category} - {self.bought_from or 'N/A'})"


class Lot(BaseModel):
    class PaymentStatus(models.TextChoices):
        PAYMENT_PENDING = "payment_pending", _("Payment Pending")
        PARTIALLY_PAID = "partially_paid", _("Partially Paid")
        PAID = "paid", _("Paid")

    title = models.CharField(max_length=255)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    bought_on = models.DateField()
    bought_from = models.CharField(max_length=255, null=True, blank=True)
    paid_on = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=50,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PAYMENT_PENDING
    )

    def __str__(self):
        return f"{self.title} - {self.bought_on}"

    def get_total_payments(self):
        """Calculate total amount paid for this lot"""
        return self.payments.aggregate(total=Sum('amount'))['total'] or 0

    def update_payment_status(self):
        """Update payment status based on total payments"""
        total_paid = self.get_total_payments()
        
        if total_paid == 0:
            self.status = self.PaymentStatus.PAYMENT_PENDING
        elif total_paid < self.total_price:
            self.status = self.PaymentStatus.PARTIALLY_PAID
        else:
            self.status = self.PaymentStatus.PAID
        
        self.save()


class Payment(BaseModel):
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=100, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Payment of {self.amount} for {self.lot.title} on {self.payment_date}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update lot payment status whenever a payment is saved
        self.lot.update_payment_status()



# billing/models.py

from django.db import models
from products.models import Product


class Purchase(models.Model):
    """
    Represents one complete bill/invoice for a customer.
    """
    customer_email = models.EmailField(db_index=True)
    total_without_tax = models.FloatField(default=0.0)
    total_tax = models.FloatField(default=0.0)
    net_total = models.FloatField(default=0.0)           # total with tax
    rounded_total = models.FloatField(default=0.0)       # rounded net total
    cash_paid = models.FloatField(default=0.0)
    balance_returned = models.FloatField(default=0.0)    # change given back
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "purchases"
        ordering = ["-created_at"]                       # latest first

    def __str__(self):
        return f"Bill #{self.id} — {self.customer_email} — ₹{self.rounded_total}"


class PurchaseItem(models.Model):
    """
    Represents a single product line inside a bill.
    We store unit_price at time of purchase because
    product price can change later — old bills must stay accurate.
    """
    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.CASCADE,
        related_name="items"                             # purchase.items.all()
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,                       # prevent deleting product if used in a bill
        related_name="purchase_items"
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.FloatField()                     # price at time of purchase
    tax_percentage = models.FloatField()                 # tax at time of purchase
    purchase_price = models.FloatField()                 # unit_price x quantity
    tax_amount = models.FloatField()                     # tax on this item
    total_price = models.FloatField()                    # purchase_price + tax_amount

    class Meta:
        db_table = "purchase_items"

    def __str__(self):
        return f"{self.product.name} x{self.quantity} — Bill #{self.purchase.id}"
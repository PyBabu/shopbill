from django.db import models


class Product(models.Model):
    name           = models.CharField(max_length=255)
    price          = models.FloatField(help_text="Price per unit")
    stock          = models.PositiveIntegerField(help_text="Available stock quantity")
    tax_percentage = models.FloatField(help_text="Tax percentage e.g. 18 for 18%")

    class Meta:
        db_table = "products"
        ordering = ["id"]         

    def __str__(self):
        return f"{self.name} (₹{self.price})"
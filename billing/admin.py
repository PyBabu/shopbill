# billing/admin.py

from django.contrib import admin
from .models import Purchase, PurchaseItem


class PurchaseItemInline(admin.TabularInline):
    model           = PurchaseItem
    extra           = 0                        # don't show empty rows
    readonly_fields = [
        "product", "quantity", "unit_price",
        "tax_percentage", "purchase_price",
        "tax_amount", "total_price"
    ]
    can_delete      = False                    # prevent accidental deletion


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display    = [
        "id", "customer_email", "rounded_total",
        "cash_paid", "balance_returned", "created_at"
    ]
    search_fields   = ["customer_email"]
    ordering        = ["-id"]                  # ← latest purchase first
    readonly_fields = [
        "total_without_tax", "total_tax", "net_total",
        "rounded_total", "balance_returned", "created_at"
    ]
    list_per_page   = 20
    inlines         = [PurchaseItemInline]
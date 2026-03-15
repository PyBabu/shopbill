from dataclasses import dataclass, field
from typing import List, Dict
from products.models import Product
from .models import Purchase, PurchaseItem


# ── Data Classes (clean data containers)
@dataclass
class BillItem:
    """Holds calculated values for one product line in the bill."""
    product: Product
    quantity: int
    unit_price: float
    tax_percentage: float
    purchase_price: float       # unit_price x quantity
    tax_amount: float           # tax on this line
    total_price: float          # purchase_price + tax_amount


@dataclass
class BillSummary:
    """Holds the complete calculated bill summary."""
    customer_email: str
    items: List[BillItem]
    total_without_tax: float
    total_tax: float
    net_total: float
    rounded_total: float
    cash_paid: float
    balance: float
    balance_denominations: Dict[int, int]   # {500: 1, 50: 2, ...}


# ── Available denominations in the shop (largest first) 
DENOMINATIONS = [500, 50, 20, 10, 5, 2, 1]


# ── Core Service Functions

def calculate_bill(
    customer_email: str,
    product_quantities: List[Dict],     # [{"product_id": 1, "quantity": 2}, ...]
    denomination_counts: Dict[int, int], # {500: 2, 50: 3, ...} — available in shop
    cash_paid: float
) -> BillSummary:
    """
    Main billing function.
    Takes raw form input, returns a fully calculated BillSummary.
    """
    items = _calculate_items(product_quantities)
    total_without_tax = round(sum(item.purchase_price for item in items), 2)
    total_tax = round(sum(item.tax_amount for item in items), 2)
    net_total = round(total_without_tax + total_tax, 2)
    rounded_total = round(net_total)                      # round to nearest rupee
    balance = round(cash_paid - rounded_total, 2)
    balance_denominations = _calculate_balance_denominations(balance, denomination_counts)

    return BillSummary(
        customer_email=customer_email,
        items=items,
        total_without_tax=total_without_tax,
        total_tax=total_tax,
        net_total=net_total,
        rounded_total=rounded_total,
        cash_paid=cash_paid,
        balance=balance,
        balance_denominations=balance_denominations,
    )


def save_bill(summary: BillSummary) -> Purchase:
    """
    Saves the calculated bill to the database.
    Returns the created Purchase object.
    """
    purchase = Purchase.objects.create(
        customer_email=summary.customer_email,
        total_without_tax=summary.total_without_tax,
        total_tax=summary.total_tax,
        net_total=summary.net_total,
        rounded_total=summary.rounded_total,
        cash_paid=summary.cash_paid,
        balance_returned=summary.balance,
    )

    # Bulk create all line items in one DB query — efficient
    PurchaseItem.objects.bulk_create([
        PurchaseItem(
            purchase=purchase,
            product=item.product,
            quantity=item.quantity,
            unit_price=item.unit_price,
            tax_percentage=item.tax_percentage,
            purchase_price=item.purchase_price,
            tax_amount=item.tax_amount,
            total_price=item.total_price,
        )
        for item in summary.items
    ])

    return purchase


# ── Private Helper Functions 

def _calculate_items(product_quantities: List[Dict]) -> List[BillItem]:
    """
    Fetches products from DB and calculates per-item values.
    Raises ValueError if product not found or quantity is invalid.
    """
    items = []

    for entry in product_quantities:
        product_id = entry.get("product_id")
        quantity = entry.get("quantity", 0)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            raise ValueError(f"Product with ID {product_id} does not exist.")

        if quantity <= 0:
            raise ValueError(f"Quantity for product '{product.name}' must be greater than 0.")

        purchase_price = round(product.price * quantity, 2)
        tax_amount = round(purchase_price * (product.tax_percentage / 100), 2)
        total_price = round(purchase_price + tax_amount, 2)

        items.append(BillItem(
            product=product,
            quantity=quantity,
            unit_price=product.price,
            tax_percentage=product.tax_percentage,
            purchase_price=purchase_price,
            tax_amount=tax_amount,
            total_price=total_price,
        ))

    return items


def _calculate_balance_denominations(
    balance: float,
    available_counts: Dict[int, int]
) -> Dict[int, int]:
    """
    Greedy algorithm to calculate which denominations to return as change.
    Uses only denominations available in the shop.

    Example:
        balance = 643, available = {500:2, 50:3, 20:5, 10:2, 5:1, 2:3, 1:5}
        Result  = {500:1, 50:2, 20:2, 2:1, 1:1}
    """
    result = {}
    remaining = int(round(balance))             # work in whole rupees

    for denomination in DENOMINATIONS:
        if remaining <= 0:
            break

        available = available_counts.get(denomination, 0)
        if available <= 0:
            continue

        needed = remaining // denomination       # how many of this note needed
        used = min(needed, available)            # can't use more than available

        if used > 0:
            result[denomination] = used
            remaining -= used * denomination

    return result
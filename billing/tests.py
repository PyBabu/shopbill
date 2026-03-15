# billing/tests.py

from django.test import TestCase, Client
from django.urls import reverse
from products.models import Product
from billing.models import Purchase, PurchaseItem
from billing.services import (
    calculate_bill,
    save_bill,
    _calculate_balance_denominations,
    _calculate_items,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Model Tests
# ─────────────────────────────────────────────────────────────────────────────

class ProductModelTest(TestCase):
    """Tests for the Product model."""

    def setUp(self):
        """Create test product — runs before every test method."""
        self.product = Product.objects.create(
            name="Rice (1kg)",
            price=60.00,
            stock=100,
            tax_percentage=5.0,
        )

    def test_product_created_successfully(self):
        """Product should be saved with correct fields."""
        self.assertEqual(self.product.name, "Rice (1kg)")
        self.assertEqual(self.product.price, 60.00)
        self.assertEqual(self.product.stock, 100)
        self.assertEqual(self.product.tax_percentage, 5.0)

    def test_product_str_representation(self):
        """__str__ should return name and price."""
        self.assertEqual(str(self.product), "Rice (1kg) (₹60.0)")

    def test_product_ordering_by_id(self):
        """Products should be ordered by ID."""
        Product.objects.create(
            name="Sugar", price=50.0, stock=80, tax_percentage=5.0
        )
        products = list(Product.objects.all())
        self.assertEqual(products[0].id, self.product.id)


class PurchaseModelTest(TestCase):
    """Tests for the Purchase model."""

    def setUp(self):
        self.purchase = Purchase.objects.create(
            customer_email="test@gmail.com",
            total_without_tax=100.0,
            total_tax=10.0,
            net_total=110.0,
            rounded_total=110.0,
            cash_paid=200.0,
            balance_returned=90.0,
        )

    def test_purchase_created_successfully(self):
        """Purchase should be saved with correct fields."""
        self.assertEqual(self.purchase.customer_email, "test@gmail.com")
        self.assertEqual(self.purchase.rounded_total, 110.0)
        self.assertEqual(self.purchase.balance_returned, 90.0)

    def test_purchase_str_representation(self):
        """__str__ should return bill number, email and total."""
        expected = f"Bill #{self.purchase.id} — test@gmail.com — ₹110.0"
        self.assertEqual(str(self.purchase), expected)

    def test_purchase_ordering_latest_first(self):
        """Latest purchase should appear first."""
        second = Purchase.objects.create(
            customer_email="second@gmail.com",
            total_without_tax=0, total_tax=0,
            net_total=0, rounded_total=0,
            cash_paid=0, balance_returned=0,
        )
        purchases = list(Purchase.objects.all())
        self.assertEqual(purchases[0].id, second.id)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Service / Business Logic Tests
# ─────────────────────────────────────────────────────────────────────────────

class CalculateItemsTest(TestCase):
    """Tests for _calculate_items helper."""

    def setUp(self):
        self.product = Product.objects.create(
            name="Rice (1kg)",
            price=60.0,
            stock=100,
            tax_percentage=5.0,
        )

    def test_correct_item_calculation(self):
        """Should correctly calculate purchase price, tax and total."""
        items = _calculate_items([
            {"product_id": self.product.id, "quantity": 2}
        ])
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.purchase_price, 120.0)   # 60 x 2
        self.assertEqual(item.tax_amount, 6.0)         # 120 x 5%
        self.assertEqual(item.total_price, 126.0)      # 120 + 6

    def test_invalid_product_id_raises_error(self):
        """Should raise ValueError for non-existent product."""
        with self.assertRaises(ValueError) as ctx:
            _calculate_items([{"product_id": 9999, "quantity": 1}])
        self.assertIn("9999", str(ctx.exception))

    def test_zero_quantity_raises_error(self):
        """Should raise ValueError when quantity is 0."""
        with self.assertRaises(ValueError):
            _calculate_items([
                {"product_id": self.product.id, "quantity": 0}
            ])

    def test_multiple_items(self):
        """Should handle multiple products correctly."""
        p2 = Product.objects.create(
            name="Sugar", price=50.0,
            stock=80, tax_percentage=18.0
        )
        items = _calculate_items([
            {"product_id": self.product.id, "quantity": 1},
            {"product_id": p2.id, "quantity": 2},
        ])
        self.assertEqual(len(items), 2)


class DenominationCalculationTest(TestCase):
    """Tests for _calculate_balance_denominations — the greedy algorithm."""

    def test_exact_change_calculation(self):
        """
        Balance 643 with enough notes should return correct denominations.
        643 = 500x1 + 50x2 + 20x2 + 2x1 + 1x1
        """
        available = {500: 5, 50: 5, 20: 5, 10: 5, 5: 5, 2: 5, 1: 5}
        result = _calculate_balance_denominations(643, available)
        self.assertEqual(result.get(500), 1)
        self.assertEqual(result.get(50), 2)
        self.assertEqual(result.get(20), 2)
        self.assertEqual(result.get(2), 1)
        self.assertEqual(result.get(1), 1)

    def test_zero_balance_returns_empty(self):
        """Zero balance should return empty dict."""
        available = {500: 5, 50: 5, 20: 5}
        result = _calculate_balance_denominations(0, available)
        self.assertEqual(result, {})

    def test_limited_denominations(self):
        """Should not use more notes than available."""
        # Only 1x500 available, balance=1000 → should use 1x500 then stop
        available = {500: 1, 50: 0, 20: 0, 10: 0, 5: 0, 2: 0, 1: 0}
        result = _calculate_balance_denominations(1000, available)
        self.assertEqual(result.get(500), 1)
        # remaining 500 cannot be given — no other notes available
        total_returned = sum(k * v for k, v in result.items())
        self.assertEqual(total_returned, 500)

    def test_small_balance(self):
        """Balance of 7 = 5x1 + 2x1."""
        available = {500: 5, 50: 5, 20: 5, 10: 5, 5: 5, 2: 5, 1: 5}
        result = _calculate_balance_denominations(7, available)
        self.assertEqual(result.get(5), 1)
        self.assertEqual(result.get(2), 1)


class CalculateBillTest(TestCase):
    """Tests for the main calculate_bill function."""

    def setUp(self):
        self.product = Product.objects.create(
            name="Rice (1kg)",
            price=60.0,
            stock=100,
            tax_percentage=5.0,
        )
        self.denominations = {
            500: 5, 50: 5, 20: 5,
            10: 5, 5: 5, 2: 5, 1: 5
        }

    def test_full_bill_calculation(self):
        """Full bill should calculate all fields correctly."""
        summary = calculate_bill(
            customer_email="test@gmail.com",
            product_quantities=[
                {"product_id": self.product.id, "quantity": 2}
            ],
            denomination_counts=self.denominations,
            cash_paid=200.0,
        )
        self.assertEqual(summary.total_without_tax, 120.0)  # 60 x 2
        self.assertEqual(summary.total_tax, 6.0)            # 120 x 5%
        self.assertEqual(summary.net_total, 126.0)
        self.assertEqual(summary.rounded_total, 126)
        self.assertEqual(summary.balance, 74)               # 200 - 126
        self.assertEqual(summary.customer_email, "test@gmail.com")

    def test_balance_denomination_populated(self):
        """Balance denominations should not be empty when change is due."""
        summary = calculate_bill(
            customer_email="test@gmail.com",
            product_quantities=[
                {"product_id": self.product.id, "quantity": 1}
            ],
            denomination_counts=self.denominations,
            cash_paid=500.0,
        )
        self.assertGreater(summary.balance, 0)
        self.assertGreater(len(summary.balance_denominations), 0)

    def test_no_change_when_exact_payment(self):
        """No denominations when exact cash is paid."""
        # Rice x1 = 60 + 5% tax = 63
        summary = calculate_bill(
            customer_email="test@gmail.com",
            product_quantities=[
                {"product_id": self.product.id, "quantity": 1}
            ],
            denomination_counts=self.denominations,
            cash_paid=63.0,
        )
        self.assertEqual(summary.balance, 0)
        self.assertEqual(summary.balance_denominations, {})


class SaveBillTest(TestCase):
    """Tests for save_bill — database persistence."""

    def setUp(self):
        self.product = Product.objects.create(
            name="Rice (1kg)",
            price=60.0,
            stock=100,
            tax_percentage=5.0,
        )

    def test_bill_saved_to_database(self):
        """save_bill should create Purchase and PurchaseItem records."""
        summary = calculate_bill(
            customer_email="test@gmail.com",
            product_quantities=[
                {"product_id": self.product.id, "quantity": 2}
            ],
            denomination_counts={500: 5, 50: 5},
            cash_paid=500.0,
        )
        purchase = save_bill(summary)

        # Purchase exists in DB
        self.assertIsNotNone(purchase.id)
        self.assertEqual(purchase.customer_email, "test@gmail.com")
        self.assertEqual(purchase.rounded_total, 126)

        # PurchaseItem created
        self.assertEqual(purchase.items.count(), 1)
        item = purchase.items.first()
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, 60.0)

    def test_multiple_items_saved(self):
        """All purchase items should be saved correctly."""
        p2 = Product.objects.create(
            name="Sugar", price=50.0,
            stock=80, tax_percentage=18.0
        )
        summary = calculate_bill(
            customer_email="test@gmail.com",
            product_quantities=[
                {"product_id": self.product.id, "quantity": 1},
                {"product_id": p2.id, "quantity": 2},
            ],
            denomination_counts={500: 5, 50: 5},
            cash_paid=1000.0,
        )
        purchase = save_bill(summary)
        self.assertEqual(purchase.items.count(), 2)


# ─────────────────────────────────────────────────────────────────────────────
# 3. View Tests
# ─────────────────────────────────────────────────────────────────────────────

class BillFormViewTest(TestCase):
    """Tests for the billing form view."""

    def setUp(self):
        self.client = Client()
        self.product = Product.objects.create(
            name="Rice (1kg)",
            price=60.0,
            stock=100,
            tax_percentage=5.0,
        )
        self.url = reverse("billing:bill_form")

    def test_get_request_returns_form(self):
        """GET should return 200 with billing form."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "billing/bill_form.html")

    def test_post_valid_data_generates_bill(self):
        """Valid POST should generate bill and show result page."""
        response = self.client.post(self.url, {
            "customer_email":        "test@gmail.com",
            "cash_paid":             "500",
            f"product_id_0":         str(self.product.id),
            f"quantity_0":           "2",
            "denomination_500":      "5",
            "denomination_50":       "5",
            "denomination_20":       "5",
            "denomination_10":       "5",
            "denomination_5":        "5",
            "denomination_2":        "5",
            "denomination_1":        "5",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "billing/bill_result.html")
        self.assertIn("summary", response.context)

    def test_post_no_products_shows_error(self):
        """POST with no products should show error message."""
        response = self.client.post(self.url, {
            "customer_email":   "test@gmail.com",
            "cash_paid":        "500",
            "denomination_500": "5",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "billing/bill_form.html")

    def test_post_insufficient_cash_shows_error(self):
        """POST with cash less than total should show error."""
        response = self.client.post(self.url, {
            "customer_email":   "test@gmail.com",
            "cash_paid":        "10",            # way less than bill
            f"product_id_0":    str(self.product.id),
            f"quantity_0":      "10",
            "denomination_500": "5",
            "denomination_50":  "5",
            "denomination_20":  "5",
            "denomination_10":  "5",
            "denomination_5":   "5",
            "denomination_2":   "5",
            "denomination_1":   "5",
        })
        messages = list(response.context["messages"])
        self.assertTrue(len(messages) > 0)


class PurchaseSearchViewTest(TestCase):
    """Tests for purchase history search view."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("purchases:search")
        self.purchase = Purchase.objects.create(
            customer_email="test@gmail.com",
            total_without_tax=100.0,
            total_tax=10.0,
            net_total=110.0,
            rounded_total=110.0,
            cash_paid=200.0,
            balance_returned=90.0,
        )

    def test_get_without_email_shows_empty(self):
        """GET without email should show empty results."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "purchases/search.html")

    def test_search_by_email_returns_results(self):
        """Searching by email should return matching purchases."""
        response = self.client.get(self.url, {"email": "test@gmail.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["purchases"]), 1)

    def test_search_wrong_email_returns_empty(self):
        """Searching wrong email should return no results."""
        response = self.client.get(self.url, {"email": "wrong@gmail.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["purchases"]), 0)

    def test_search_case_insensitive(self):
        """Email search should be case insensitive."""
        response = self.client.get(self.url, {"email": "TEST@GMAIL.COM"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["purchases"]), 1)


class PurchaseDetailViewTest(TestCase):
    """Tests for purchase detail view."""

    def setUp(self):
        self.client = Client()
        self.purchase = Purchase.objects.create(
            customer_email="test@gmail.com",
            total_without_tax=100.0,
            total_tax=10.0,
            net_total=110.0,
            rounded_total=110.0,
            cash_paid=200.0,
            balance_returned=90.0,
        )

    def test_detail_view_returns_correct_purchase(self):
        """Detail view should return correct purchase."""
        url = reverse("purchases:detail", args=[self.purchase.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "purchases/detail.html")
        self.assertEqual(
            response.context["purchase"].id,
            self.purchase.id
        )

    def test_invalid_purchase_id_returns_404(self):
        """Invalid purchase ID should return 404."""
        url = reverse("purchases:detail", args=[9999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
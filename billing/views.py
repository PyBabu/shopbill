from django.shortcuts import render
from django.contrib import messages

from products.models import Product
from .forms import BillForm
from .services import calculate_bill, save_bill
from .tasks import send_invoice_email_task


def bill_form_view(request):
    """
    GET  → Show the empty billing form (Page 1)
    POST → Calculate bill, save to DB, trigger async email, show result (Page 2)
    """
    if request.method == "POST":
        form = BillForm(request.POST)

        if form.is_valid():
            # ── Parse product rows from POST data ──
            product_quantities = _parse_product_rows(request.POST)

            if not product_quantities:
                messages.error(request, "Please add at least one product to the bill.")
                return render(request, "billing/bill_form.html", {
                    "form": form,
                    "products": Product.objects.all().order_by("id"),
                })

            try:
                # ── Calculate bill ──
                summary = calculate_bill(
                    customer_email=form.cleaned_data["customer_email"],
                    product_quantities=product_quantities,
                    denomination_counts=form.get_denomination_counts(),
                    cash_paid=form.cleaned_data["cash_paid"],
                )

                # ── Validate cash paid is enough ──
                if summary.cash_paid < summary.rounded_total:
                    messages.error(
                        request,
                        f"Cash paid ₹{summary.cash_paid} is less than "
                        f"bill total ₹{summary.rounded_total}."
                    )
                    return render(request, "billing/bill_form.html", {
                        "form": form,
                        "products": Product.objects.all().order_by("id"),
                    })

                # ── Save to database ───
                purchase = save_bill(summary)

                # ── Send invoice email asynchronously (Celery task) ─────────
                send_invoice_email_task.delay(purchase.id)

                # ── Show result page ───
                return render(request, "billing/bill_result.html", {
                    "summary": summary,
                    "purchase": purchase,
                })

            except ValueError as e:
                messages.error(request, str(e))
                return render(request, "billing/bill_form.html", {
                    "form": form,
                    "products": Product.objects.all().order_by("id"),
                })

    else:
        form = BillForm()

    # ── GET request ───
    return render(request, "billing/bill_form.html", {
        "form": form,
        "products": Product.objects.all().order_by("id"),
    })


# ── Private Helpers ──

def _parse_product_rows(post_data) -> list:
    """
    Extracts product rows from POST data.

    The form sends dynamic rows as:
        product_id_0=1, quantity_0=2
        product_id_1=4, quantity_1=3
        ...
    This function collects all valid rows into a clean list.
    """
    product_quantities = []
    index = 0

    while True:
        product_id = post_data.get(f"product_id_{index}")
        quantity   = post_data.get(f"quantity_{index}")

        if product_id is None:      # no more rows — stop
            break

        # Skip completely empty rows
        if product_id.strip() and quantity.strip():
            try:
                product_quantities.append({
                    "product_id": int(product_id),
                    "quantity":   int(quantity),
                })
            except ValueError:
                pass                # skip malformed rows silently

        index += 1

    return product_quantities
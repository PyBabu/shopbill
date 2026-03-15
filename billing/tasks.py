# billing/tasks.py

import logging
from celery import shared_task
from django.core.mail import EmailMessage
from .models import Purchase
from .invoice_pdf import generate_invoice_pdf

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_invoice_email_task(self, purchase_id: int):
    """
    Async Celery task — generates PDF invoice and emails it to customer.
    """
    try:
        purchase = Purchase.objects.prefetch_related(
            "items__product"
        ).get(id=purchase_id)

        # ── Generate PDF ───
        pdf_bytes = generate_invoice_pdf(purchase)

        # ── Build Email ───
        email = EmailMessage(
            subject=f"Your Invoice #{purchase.id} — ShopBill",
            body=(
                f"Dear Customer,\n\n"
                f"Thank you for shopping with us!\n"
                f"Please find your invoice #{purchase.id} attached.\n\n"
                f"Bill Summary:\n"
                f"  Total Amount : Rs.{purchase.rounded_total:.2f}\n"
                f"  Cash Paid    : Rs.{purchase.cash_paid:.2f}\n"
                f"  Balance      : Rs.{purchase.balance_returned:.2f}\n\n"
                f"Regards,\nShopBill Team"
            ),
            from_email=None,
            to=[purchase.customer_email],
        )

        # ── Attach PDF ───
        email.attach(
            filename=f"invoice_{purchase.id}.pdf",
            content=pdf_bytes,
            mimetype="application/pdf",
        )

        email.send(fail_silently=False)

        logger.info(
            f"PDF Invoice email sent for purchase "
            f"#{purchase_id} to {purchase.customer_email}"
        )

    except Purchase.DoesNotExist:
        logger.error(f"Purchase #{purchase_id} not found. Email not sent.")

    except Exception as exc:
        logger.error(
            f"Failed to send invoice email for "
            f"purchase #{purchase_id}: {exc}"
        )
        raise self.retry(exc=exc)
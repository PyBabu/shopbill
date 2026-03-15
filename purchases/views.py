from django.shortcuts import render, get_object_or_404
from billing.models import Purchase


def purchase_search_view(request):
    """
    Search past purchases by customer email.
    """
    email = request.GET.get("email", "").strip()
    purchases = []

    if email:
        purchases = Purchase.objects.filter(
            customer_email__iexact=email      # case insensitive match
        ).prefetch_related("items__product")  # avoid N+1 queries

    return render(request, "purchases/search.html", {
        "purchases": purchases,
        "searched_email": email,
    })


def purchase_detail_view(request, purchase_id):
    """
    Show all items in a specific purchase.
    """
    purchase = get_object_or_404(
        Purchase.objects.prefetch_related("items__product"),
        id=purchase_id
    )

    return render(request, "purchases/detail.html", {
        "purchase": purchase,
    })
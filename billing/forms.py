# billing/forms.py

from django import forms
from billing.services import DENOMINATIONS


class BillForm(forms.Form):
    """
    Main billing form — Page 1.
    Product rows are handled dynamically in the template via JavaScript.
    """
    customer_email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "Email ID"})
    )
    cash_paid = forms.FloatField(
        min_value=0.01,
        widget=forms.NumberInput(attrs={"placeholder": "Amount", "step": "0.01"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for denomination in DENOMINATIONS:
            self.fields[f"denomination_{denomination}"] = forms.IntegerField(
                min_value=0,
                initial=10,                     # ← default 10 notes available
                required=False,
                widget=forms.NumberInput(attrs={
                    "placeholder": "Count",
                    "min": "0"
                })
            )

    def get_denomination_fields(self):
        """Helper used in template to render denomination rows cleanly."""
        return [
            (denomination, self[f"denomination_{denomination}"])
            for denomination in DENOMINATIONS
        ]

    def get_denomination_counts(self) -> dict:
        """Returns cleaned denomination counts as {500: 10, 50: 10, ...}"""
        counts = {}
        for denomination in DENOMINATIONS:
            value = self.cleaned_data.get(f"denomination_{denomination}", 0)
            counts[denomination] = int(value) if value else 0
        return counts
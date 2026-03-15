# billing/urls.py

from django.urls import path
from . import views

app_name = "billing"

urlpatterns = [
    path("", views.bill_form_view, name="bill_form"),
]
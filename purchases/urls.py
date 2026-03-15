from django.urls import path
from . import views

app_name = "purchases"

urlpatterns = [
    path("", views.purchase_search_view, name="search"),
    path("<int:purchase_id>/", views.purchase_detail_view, name="detail"),
]
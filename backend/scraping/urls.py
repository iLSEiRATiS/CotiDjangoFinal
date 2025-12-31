from django.urls import path

from .views import CompararPrecios

urlpatterns = [
    path("comparar/<str:nombre>/", CompararPrecios.as_view(), name="comparar-precios"),
]

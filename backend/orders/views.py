from rest_framework import viewsets, permissions, filters

from .models import Order
from .serializers import OrderSerializer
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.prefetch_related("items__product").select_related("user")
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["nombre", "email", "status"]
    ordering_fields = ["creado_en", "total", "status"]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class MyOrdersView(LoginRequiredMixin, generic.ListView):
    model = Order
    template_name = "account/orders.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items__product")

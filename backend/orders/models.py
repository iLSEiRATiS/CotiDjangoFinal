from django.conf import settings
from django.db import models
from django.utils import timezone

from products.models import Product


class Order(models.Model):
    STATUS_CHOICES = [
        ("created", "Creado"),
        ("approved", "Aprobado"),
        ("draft", "Borrador"),
        ("paid", "Pagado"),
        ("shipped", "Enviado"),
        ("delivered", "Entregado"),
        ("cancelled", "Cancelado"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    nombre = models.CharField(max_length=120)
    email = models.EmailField()
    direccion = models.CharField(max_length=255)
    ciudad = models.CharField(max_length=120)
    estado = models.CharField(max_length=120, blank=True)
    cp = models.CharField(max_length=20, blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    nota = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="created")
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    creado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Pedido #{self.id or ''} - {self.nombre}"

    def recalc_total(self):
        total = sum(item.subtotal for item in self.items.all())
        self.total = total
        self.save(update_fields=["total"])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad

    def __str__(self):
        return f"{self.product} x{self.cantidad}"

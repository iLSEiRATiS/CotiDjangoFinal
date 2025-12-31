from rest_framework import serializers

from .models import Order, OrderItem
from products.serializers import ProductSerializer
from products.models import Product


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        source="product", queryset=Product.objects.all(), write_only=True
    )
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_id", "cantidad", "precio_unitario", "subtotal"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "nombre",
            "email",
            "direccion",
            "ciudad",
            "estado",
            "cp",
            "telefono",
            "nota",
            "status",
            "total",
            "creado_en",
            "items",
        ]
        read_only_fields = ["user", "total", "creado_en"]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        order = Order.objects.create(**validated_data)
        for item in items_data:
            product = item["product"]
            OrderItem.objects.create(
                order=order,
                product=product,
                cantidad=item.get("cantidad", 1),
                precio_unitario=item.get("precio_unitario", product.precio),
            )
        order.recalc_total()
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                product = item["product"]
                OrderItem.objects.create(
                    order=instance,
                    product=product,
                    cantidad=item.get("cantidad", 1),
                    precio_unitario=item.get("precio_unitario", product.precio),
                )
        instance.recalc_total()
        return instance

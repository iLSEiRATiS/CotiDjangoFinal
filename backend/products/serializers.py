from rest_framework import serializers

from .models import Product, Category, Offer


class CategorySerializer(serializers.ModelSerializer):
    parent = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), allow_null=True, required=False)

    class Meta:
        model = Category
        fields = ["id", "nombre", "slug", "descripcion", "parent"]


class OfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Offer
        fields = [
            "id",
            "nombre",
            "slug",
            "descripcion",
            "porcentaje",
            "producto",
            "categoria",
            "activo",
            "empieza",
            "termina",
            "creado_en",
        ]


class ProductSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    categoria = CategorySerializer(read_only=True)
    categoria_id = serializers.PrimaryKeyRelatedField(
        source="categoria", queryset=Category.objects.all(), write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "user",
            "categoria",
            "categoria_id",
            "nombre",
            "slug",
            "precio",
            "descripcion",
            "imagen",
            "stock",
            "activo",
            "creado_en",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return data

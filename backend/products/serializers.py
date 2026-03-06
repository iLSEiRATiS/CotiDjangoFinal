from rest_framework import serializers

from .models import Product, ProductImage, Category, Offer


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
    images = serializers.SerializerMethodField()

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
            "image_url",
            "images",
            "atributos",
            "atributos_stock",
            "stock",
            "activo",
            "creado_en",
        ]

    def get_images(self, instance):
        out = []
        seen = set()

        def append_url(value):
            url = str(value or "").strip()
            if not url or url in seen:
                return
            seen.add(url)
            out.append(url)

        append_url(getattr(instance, "image_url", ""))
        if instance.imagen:
            try:
                append_url(instance.imagen.url)
            except Exception:
                pass

        queryset = getattr(instance, "extra_images", None)
        if queryset is None:
            queryset = ProductImage.objects.filter(product=instance)
        for img in queryset.filter(activo=True).order_by("order", "id"):
            append_url(getattr(img, "image_url", ""))
            if img.image:
                try:
                    append_url(img.image.url)
                except Exception:
                    pass
        return out

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return data

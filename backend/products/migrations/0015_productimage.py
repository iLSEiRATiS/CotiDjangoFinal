from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0014_alter_category_nombre_alter_product_image_url_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(blank=True, null=True, upload_to="products/gallery/")),
                ("image_url", models.URLField(blank=True, default="", max_length=500)),
                ("order", models.PositiveIntegerField(default=0)),
                ("activo", models.BooleanField(default=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "product",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="extra_images", to="products.product"),
                ),
            ],
            options={
                "verbose_name": "Imagen de producto",
                "verbose_name_plural": "Imagenes de producto",
                "ordering": ["order", "id"],
            },
        ),
    ]

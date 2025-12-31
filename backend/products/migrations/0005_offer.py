from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0004_category_parent_product_slug"),
    ]

    operations = [
        migrations.CreateModel(
            name="Offer",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=120)),
                ("slug", models.SlugField(blank=True, max_length=140, unique=True)),
                ("descripcion", models.TextField(blank=True)),
                ("porcentaje", models.DecimalField(decimal_places=2, max_digits=5, help_text="Ej: 10.00 para 10%")),
                ("activo", models.BooleanField(default=True)),
                ("empieza", models.DateTimeField(blank=True, null=True)),
                ("termina", models.DateTimeField(blank=True, null=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "categoria",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ofertas",
                        to="products.category",
                    ),
                ),
                (
                    "producto",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ofertas",
                        to="products.product",
                    ),
                ),
            ],
            options={
                "ordering": ["-creado_en"],
            },
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0021_product_atributos_precio"),
    ]

    operations = [
        migrations.CreateModel(
            name="StoreSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("min_order_amount", models.DecimalField(decimal_places=2, default=50000, help_text="Monto minimo requerido para permitir compras.", max_digits=12, verbose_name="monto minimo de compra")),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Configuracion de tienda",
                "verbose_name_plural": "Configuracion de tienda",
            },
        ),
    ]

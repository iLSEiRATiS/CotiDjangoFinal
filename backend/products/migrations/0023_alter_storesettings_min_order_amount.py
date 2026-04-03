from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0022_storesettings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="storesettings",
            name="min_order_amount",
            field=models.DecimalField(decimal_places=2, default=100000, help_text="Monto minimo requerido para permitir compras.", max_digits=12, verbose_name="monto minimo de compra"),
        ),
    ]

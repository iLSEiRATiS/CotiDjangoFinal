from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0010_product_atributos"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="atributos_stock",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]


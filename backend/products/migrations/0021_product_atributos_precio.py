from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0020_suppliercontact"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="atributos_precio",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_alter_order_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="atributos",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]


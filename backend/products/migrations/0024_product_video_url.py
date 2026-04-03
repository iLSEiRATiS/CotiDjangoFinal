from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0023_alter_storesettings_min_order_amount"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="video_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
    ]

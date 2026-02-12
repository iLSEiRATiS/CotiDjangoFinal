from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0009_alter_category_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="atributos",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]


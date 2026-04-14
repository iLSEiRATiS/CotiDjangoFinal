from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0010_customuser_shipping_quote_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="document_number",
            field=models.CharField(blank=True, default="", max_length=40, verbose_name="dni/cuil"),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0009_backfill_user_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="shipping_quote_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name="presupuesto de envio"),
        ),
        migrations.AddField(
            model_name="customuser",
            name="shipping_quote_note",
            field=models.TextField(blank=True, default="", verbose_name="detalle de envio"),
        ),
        migrations.AddField(
            model_name="customuser",
            name="shipping_quote_updated_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="presupuesto de envio actualizado el"),
        ),
    ]

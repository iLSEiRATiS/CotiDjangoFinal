from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0008_order_envio"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="destinatario_documento",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="order",
            name="remitente_documento",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="order",
            name="remitente_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="order",
            name="remitente_nombre",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AddField(
            model_name="order",
            name="remitente_telefono",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
    ]

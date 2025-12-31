from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_alter_order_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("created", "Creado"),
                    ("approved", "Aprobado"),
                    ("draft", "Borrador"),
                    ("paid", "Pagado"),
                    ("shipped", "Enviado"),
                    ("delivered", "Entregado"),
                    ("cancelled", "Cancelado"),
                ],
                default="created",
                max_length=20,
            ),
        ),
    ]

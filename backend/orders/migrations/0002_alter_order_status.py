from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("created", "Creado"),
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

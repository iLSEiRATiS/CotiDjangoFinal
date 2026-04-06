from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0007_alter_order_options_alter_orderitem_options"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE orders_order "
                        "ADD COLUMN IF NOT EXISTS envio numeric(10, 2) NOT NULL DEFAULT 0"
                    ),
                    reverse_sql=(
                        "ALTER TABLE orders_order "
                        "DROP COLUMN IF EXISTS envio"
                    ),
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="order",
                    name="envio",
                    field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
                ),
            ],
        ),
    ]

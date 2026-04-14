from django.db import migrations, models


def _add_envio_column(apps, schema_editor):
    connection = schema_editor.connection
    table_name = "orders_order"
    with connection.cursor() as cursor:
        columns = {
            info.name
            for info in connection.introspection.get_table_description(cursor, table_name)
        }
    if "envio" in columns:
        return
    if connection.vendor == "sqlite":
        schema_editor.execute(
            "ALTER TABLE orders_order ADD COLUMN envio decimal NOT NULL DEFAULT 0"
        )
        return
    schema_editor.execute(
        "ALTER TABLE orders_order ADD COLUMN IF NOT EXISTS envio numeric(10, 2) NOT NULL DEFAULT 0"
    )


def _drop_envio_column(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == "sqlite":
        return
    schema_editor.execute("ALTER TABLE orders_order DROP COLUMN IF EXISTS envio")


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0007_alter_order_options_alter_orderitem_options"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(_add_envio_column, _drop_envio_column),
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

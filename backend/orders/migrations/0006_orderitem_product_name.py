from django.db import migrations, models


def copy_product_names(apps, schema_editor):
    OrderItem = apps.get_model("orders", "OrderItem")
    for item in OrderItem.objects.select_related("product").all().iterator():
        if item.product_id and item.product and not item.product_name:
            item.product_name = item.product.nombre or ""
            item.save(update_fields=["product_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_alter_order_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="product_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.RunPython(copy_product_names, migrations.RunPython.noop),
    ]

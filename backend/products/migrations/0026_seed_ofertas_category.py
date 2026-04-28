from django.db import migrations


def seed_ofertas_category(apps, schema_editor):
    Category = apps.get_model("products", "Category")
    exists = Category.objects.filter(parent__isnull=True, slug="ofertas").exists()
    if not exists:
        Category.objects.create(nombre="Ofertas", slug="ofertas", descripcion="")


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0025_offer_precio_oferta"),
    ]

    operations = [
        migrations.RunPython(seed_ofertas_category, migrations.RunPython.noop),
    ]

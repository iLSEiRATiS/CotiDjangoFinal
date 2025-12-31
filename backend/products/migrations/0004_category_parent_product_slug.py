from django.db import migrations, models
from django.utils.text import slugify


def populate_slugs(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    for p in Product.objects.all():
        raw = slugify(p.nombre)[:100] or f"prod-{p.pk}"
        candidate = raw
        i = 1
        while Product.objects.filter(slug=candidate).exclude(pk=p.pk).exists():
            i += 1
            candidate = f"{raw}-{i}"
        p.slug = candidate
        p.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_category_product_activo_product_stock_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='parent',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='children', to='products.category'),
        ),
        migrations.AddField(
            model_name='product',
            name='slug',
            field=models.SlugField(blank=True, max_length=120, null=True, unique=True),
        ),
        migrations.RunPython(populate_slugs, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='product',
            name='slug',
            field=models.SlugField(blank=True, max_length=120, unique=True),
        ),
    ]

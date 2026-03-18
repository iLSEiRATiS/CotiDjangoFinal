from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0015_productimage"),
    ]

    operations = [
        migrations.CreateModel(
            name="HomeMarquee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.CharField(blank=True, default="", max_length=255)),
                ("text_color", models.CharField(default="#ffffff", max_length=7)),
                ("background_color", models.CharField(default="#dc3545", max_length=7)),
                ("activo", models.BooleanField(default=False)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Marquee Home",
                "verbose_name_plural": "Marquee Home",
            },
        ),
    ]

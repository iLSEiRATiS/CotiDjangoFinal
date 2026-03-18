from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0016_homemarquee"),
    ]

    operations = [
        migrations.CreateModel(
            name="JobApplication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=120)),
                ("apellido", models.CharField(max_length=120)),
                ("telefono", models.CharField(max_length=40)),
                ("mensaje", models.TextField()),
                ("cv", models.FileField(blank=True, null=True, upload_to="job_applications/cv/")),
                ("revisado", models.BooleanField(default=False)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Postulacion",
                "verbose_name_plural": "Postulaciones",
                "ordering": ["-creado_en"],
            },
        ),
    ]

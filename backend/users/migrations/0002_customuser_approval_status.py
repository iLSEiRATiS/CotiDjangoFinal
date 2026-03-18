from django.db import migrations, models


def set_existing_users_approved(apps, schema_editor):
    CustomUser = apps.get_model("users", "CustomUser")
    CustomUser.objects.all().update(approval_status="approved")


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="approval_status",
            field=models.CharField(
                choices=[("pending", "Pendiente"), ("approved", "Aprobado"), ("rejected", "Rechazado")],
                default="pending",
                max_length=10,
            ),
        ),
        migrations.RunPython(set_existing_users_approved, migrations.RunPython.noop),
    ]

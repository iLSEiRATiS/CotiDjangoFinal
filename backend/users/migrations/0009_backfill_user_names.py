from django.db import migrations


def split_name(value):
    raw = str(value or "").strip()
    if not raw:
        return "", ""
    parts = [part for part in raw.split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def forwards(apps, schema_editor):
    User = apps.get_model("users", "CustomUser")
    for user in User.objects.all():
        changed = False

        first_name = str(user.first_name or "").strip()
        last_name = str(user.last_name or "").strip()
        display_name = str(user.name or "").strip()

        if not first_name or not last_name:
            inferred_first, inferred_last = split_name(display_name or user.username or user.email)
            if not first_name and inferred_first:
                user.first_name = inferred_first
                changed = True
            if not last_name and inferred_last:
                user.last_name = inferred_last
                changed = True

        full_name = " ".join(part for part in [str(user.first_name or "").strip(), str(user.last_name or "").strip()] if part).strip()
        if full_name and full_name != display_name:
            user.name = full_name
            changed = True

        if changed:
            user.save(update_fields=["first_name", "last_name", "name"])


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_customuser_last_password_changed_at_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]

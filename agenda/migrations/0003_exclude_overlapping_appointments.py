from django.db import migrations


def add_exclusion_constraint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    schema_editor.execute(
        """
        ALTER TABLE agenda_appointment
        ADD CONSTRAINT agenda_appointment_no_overlap
        EXCLUDE USING gist (
            business_id WITH =,
            tstzrange(start_at, end_at, '[)') WITH &&
        )
        WHERE (status <> 'cancelled')
        """
    )


def remove_exclusion_constraint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute(
        "ALTER TABLE agenda_appointment "
        "DROP CONSTRAINT IF EXISTS agenda_appointment_no_overlap"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("agenda", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(add_exclusion_constraint, remove_exclusion_constraint),
    ]

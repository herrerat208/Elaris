from django.db import migrations

SPECIALTIES = [
    ("Uñas", "unas", 10),
    ("Pestañas", "pestanas", 20),
    ("Cejas", "cejas", 30),
]

SERVICES = {
    "unas": [
        ("Belleza de manos", 45),
        ("Semi permanente", 60),
        ("Capping", 90),
        ("Soft gel", 90),
        ("Esculpidas en gel", 120),
        ("Esculpidas en acrílico", 120),
        ("Esculpidas en polygel", 120),
        ("Esmaltado semi en pies", 60),
        ("Service (mantenimiento/retiro)", 60),
    ],
    "pestanas": [
        ("Lifting", 60),
        ("Clásicas", 120),
        ("Efecto rímel", 120),
        ("Volumen brasilero", 150),
        ("Volumen 3D", 150),
        ("Volumen 4D", 150),
        ("Volumen 5D", 180),
        ("Foxy", 120),
        ("Efecto coreano", 120),
    ],
    "cejas": [
        ("Perfilado", 30),
        ("Laminado", 60),
        ("Henna", 45),
    ],
}


def seed_catalog(apps, schema_editor):
    Specialty = apps.get_model("catalog", "Specialty")
    ServiceTemplate = apps.get_model("catalog", "ServiceTemplate")

    for name, slug, sort_order in SPECIALTIES:
        specialty, _ = Specialty.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "sort_order": sort_order,
                "is_active": True,
            },
        )
        for index, (service_name, duration) in enumerate(SERVICES[slug], start=1):
            ServiceTemplate.objects.update_or_create(
                specialty=specialty,
                name=service_name,
                defaults={
                    "default_duration_minutes": duration,
                    "sort_order": index * 10,
                    "is_active": True,
                },
            )


def unseed_catalog(apps, schema_editor):
    Specialty = apps.get_model("catalog", "Specialty")
    ServiceTemplate = apps.get_model("catalog", "ServiceTemplate")

    slugs = [slug for _, slug, _ in SPECIALTIES]
    ServiceTemplate.objects.filter(specialty__slug__in=slugs).delete()
    Specialty.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_catalog, unseed_catalog),
    ]

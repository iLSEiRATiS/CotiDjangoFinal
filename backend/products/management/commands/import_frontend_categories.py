from django.core.management.base import BaseCommand
from django.utils.text import slugify

from products.models import Category


class Command(BaseCommand):
    help = "Importa las categorías definidas en Frontend/src/data/categorias.js al admin de Django."

    FRONTEND_CATS = [
        {
            "nombre": "Cotillón",
            "subcategorias": [
                {
                    "nombre": "Velas",
                    "hijos": [
                        "Velas con Palito",
                        "Velas Importadas",
                        "Bengalas",
                        "Velas con Luz",
                        "Vela Escudo de Futbol",
                        "Velas Estrellita",
                    ],
                },
                "Vinchas y Coronas",
                "Gorros y Sombreros",
                "Antifaces",
                "Carioca",
            ],
        },
        {
            "nombre": "Globos y Piñatas",
            "subcategorias": [
                "Número Metalizados",
                "Globos con Forma",
                "Set de Globos",
                {"nombre": "9 Pulgadas", "hijos": ["Perlado"]},
            ],
        },
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Elimina categorías existentes antes de importar.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            Category.objects.all().delete()
            self.stdout.write(self.style.WARNING("Categorías eliminadas (reset)."))

        created, existing = 0, 0

        def ensure_category(name, parent=None):
            slug = slugify(name)
            obj, was_created = Category.objects.get_or_create(
                slug=slug,
                defaults={"nombre": name, "parent": parent},
            )
            if not was_created and (obj.nombre != name or obj.parent != parent):
                obj.nombre = name
                obj.parent = parent
                obj.save()
            return obj, was_created

        for cat in self.FRONTEND_CATS:
            cat_obj, was_created = ensure_category(cat["nombre"])
            created += int(was_created)
            existing += int(not was_created)
            for sub in cat.get("subcategorias", []):
                if isinstance(sub, str):
                    sub_obj, sub_created = ensure_category(sub, parent=cat_obj)
                    created += int(sub_created)
                    existing += int(not sub_created)
                    continue
                sub_obj, sub_created = ensure_category(sub["nombre"], parent=cat_obj)
                created += int(sub_created)
                existing += int(not sub_created)
                for leaf in sub.get("hijos", []):
                    leaf_obj, leaf_created = ensure_category(leaf, parent=sub_obj)
                    created += int(leaf_created)
                    existing += int(not leaf_created)

        self.stdout.write(self.style.SUCCESS(f"Categorías importadas. Nuevas: {created}, existentes: {existing}"))

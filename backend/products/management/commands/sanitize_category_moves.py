from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import Category, Product


class Command(BaseCommand):
    help = (
        "Aplica movimientos seguros de categorias ya validados localmente "
        "sin tocar productos fuera del alcance definido."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Ejecuta los cambios. Sin este flag solo informa lo que haria.",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options.get("apply"))
        operations = [
            {
                "source_name": "Bengalas",
                "source_parent_name": "Velas",
                "target_name": "Bengalas",
                "target_parent_name": None,
                "delete_source_if_empty": True,
                "label": "Mover productos de Velas > Bengalas a Bengalas",
            },
            {
                "source_name": "Librería y Manualidades",
                "source_parent_name": None,
                "target_name": "Artículos Para Manualidades",
                "target_parent_name": None,
                "delete_source_if_empty": True,
                "label": "Mover productos de Librería y Manualidades a Artículos Para Manualidades",
            },
        ]

        self.stdout.write(
            self.style.WARNING(
                "MODO APLICACION" if apply_changes else "MODO SIMULACION"
            )
        )

        with transaction.atomic():
            total_moved = 0
            total_deleted_categories = 0

            for operation in operations:
                moved, deleted = self._run_operation(operation, apply_changes=apply_changes)
                total_moved += moved
                total_deleted_categories += deleted

            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Resumen: productos a mover/movidos={total_moved}, "
                    f"categorias a eliminar/eliminadas={total_deleted_categories}"
                )
            )

            if not apply_changes:
                transaction.set_rollback(True)
                self.stdout.write(
                    self.style.WARNING("Simulacion finalizada. No se guardaron cambios.")
                )

    def _find_category(self, *, name, parent_name, required=True):
        queryset = Category.objects.filter(nombre=name)
        if parent_name is None:
            queryset = queryset.filter(parent__isnull=True)
        else:
            queryset = queryset.filter(parent__nombre=parent_name)

        matches = list(queryset.select_related("parent"))
        if not matches:
            if not required:
                return None
            parent_label = "sin padre" if parent_name is None else f"con padre {parent_name}"
            raise CommandError(f"No se encontro la categoria '{name}' {parent_label}.")
        if len(matches) > 1:
            parent_label = "sin padre" if parent_name is None else f"con padre {parent_name}"
            raise CommandError(f"Se encontraron multiples categorias '{name}' {parent_label}.")
        return matches[0]

    def _run_operation(self, operation, *, apply_changes):
        source = self._find_category(
            name=operation["source_name"],
            parent_name=operation["source_parent_name"],
            required=False,
        )
        target = self._find_category(
            name=operation["target_name"],
            parent_name=operation["target_parent_name"],
        )

        if source is None:
            self.stdout.write("")
            self.stdout.write(operation["label"])
            self.stdout.write("- estado: ya aplicado o categoria origen inexistente")
            self.stdout.write(
                f"- destino vigente: {target.id} / {target.nombre} / parent={target.parent_id or '-'}"
            )
            return 0, 0

        products_qs = Product.objects.filter(categoria=source).order_by("nombre", "id")
        product_rows = list(products_qs.values_list("id", "nombre"))

        self.stdout.write("")
        self.stdout.write(operation["label"])
        self.stdout.write(
            f"- origen: {source.id} / {source.nombre} / parent={source.parent_id or '-'}"
        )
        self.stdout.write(
            f"- destino: {target.id} / {target.nombre} / parent={target.parent_id or '-'}"
        )
        self.stdout.write(f"- productos involucrados: {len(product_rows)}")

        for product_id, name in product_rows[:20]:
            self.stdout.write(f"  - {product_id}: {name}")
        hidden_count = max(len(product_rows) - 20, 0)
        if hidden_count:
            self.stdout.write(f"  - ... y {hidden_count} mas")

        moved = len(product_rows)
        deleted = 0

        if apply_changes and product_rows:
            products_qs.update(categoria=target)

        source.refresh_from_db()
        source_products_after = Product.objects.filter(categoria=source).count()
        can_delete = (
            operation.get("delete_source_if_empty", False)
            and source_products_after == 0
            and source.children.count() == 0
            and not source.ofertas.exists()
        )

        self.stdout.write(f"- origen luego del movimiento: {source_products_after} productos")
        self.stdout.write(f"- categoria origen vacia y eliminable: {'si' if can_delete else 'no'}")

        if apply_changes and can_delete:
            source.delete()
            deleted = 1
            self.stdout.write("- categoria origen eliminada")

        return moved, deleted

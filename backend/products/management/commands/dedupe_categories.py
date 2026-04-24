from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from products.models import Category, Offer, Product


class Command(BaseCommand):
    help = (
        "Detecta categorias duplicadas con el mismo nombre y el mismo padre. "
        "Por defecto solo informa; con --apply fusiona productos, ofertas e hijas "
        "en la categoria canonica de menor id."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Ejecuta las fusiones. Sin este flag solo informa lo que haria.",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options.get("apply"))
        self.stdout.write(
            self.style.WARNING("MODO APLICACION" if apply_changes else "MODO SIMULACION")
        )

        with transaction.atomic():
            reports = []
            while True:
                groups = list(self._duplicate_groups())
                if not groups:
                    break
                if not apply_changes and reports:
                    break
                for group in groups:
                    report = self._process_group(group, apply_changes=apply_changes)
                    reports.append(report)
                if not apply_changes:
                    break

            if not reports:
                self.stdout.write(self.style.SUCCESS("No se detectaron categorias duplicadas."))
            else:
                self.stdout.write("")
                self.stdout.write("Detalle final:")
                for report in reports:
                    self.stdout.write(
                        f"- {report['label']}: estado={report['status']}, "
                        f"productos={report['products_moved']}, ofertas={report['offers_moved']}, "
                        f"hijas={report['children_moved']}, eliminadas={report['deleted']}"
                    )

            if not apply_changes:
                transaction.set_rollback(True)
                self.stdout.write(
                    self.style.WARNING("Simulacion finalizada. No se guardaron cambios.")
                )

    def _duplicate_groups(self):
        return (
            Category.objects.values("nombre", "parent_id")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .order_by("parent_id", "nombre")
        )

    def _category_scope(self, *, name, parent_id):
        queryset = Category.objects.filter(nombre=name)
        if parent_id is None:
            return queryset.filter(parent__isnull=True)
        return queryset.filter(parent_id=parent_id)

    def _category_label(self, category):
        parent_name = category.parent.nombre if category.parent_id else "-"
        return f"{category.id} / {category.nombre} / parent={parent_name}"

    def _process_group(self, group, *, apply_changes):
        categories = list(
            self._category_scope(name=group["nombre"], parent_id=group["parent_id"])
            .select_related("parent")
            .order_by("id")
        )
        canonical = categories[0]
        duplicates = categories[1:]

        self.stdout.write("")
        self.stdout.write(
            f"Fusionar duplicadas: {canonical.nombre} "
            f"(parent={canonical.parent.nombre if canonical.parent_id else '-'})"
        )
        self.stdout.write(f"- canonica: {self._category_label(canonical)}")

        products_moved = 0
        offers_moved = 0
        children_moved = 0
        deleted = 0

        for source in duplicates:
            source_products = Product.objects.filter(categoria=source)
            source_offers = Offer.objects.filter(categoria=source)
            source_children = Category.objects.filter(parent=source)

            product_count = source_products.count()
            offer_count = source_offers.count()
            child_count = source_children.count()

            self.stdout.write(f"- duplicada: {self._category_label(source)}")
            self.stdout.write(
                f"  productos={product_count}, ofertas={offer_count}, hijas={child_count}"
            )

            products_moved += product_count
            offers_moved += offer_count
            children_moved += child_count

            if apply_changes:
                if product_count:
                    source_products.update(categoria=canonical)
                if offer_count:
                    source_offers.update(categoria=canonical)
                if child_count:
                    source_children.update(parent=canonical)

                source.refresh_from_db()
                if (
                    not Product.objects.filter(categoria=source).exists()
                    and not Offer.objects.filter(categoria=source).exists()
                    and not Category.objects.filter(parent=source).exists()
                ):
                    source.delete()
                    deleted += 1
                    self.stdout.write("  eliminada")

        return {
            "label": f"{canonical.nombre} / parent={canonical.parent_id or '-'}",
            "status": "applied" if apply_changes else "simulated",
            "products_moved": products_moved,
            "offers_moved": offers_moved,
            "children_moved": children_moved,
            "deleted": deleted,
        }

from collections import Counter
from pathlib import Path

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from products.models import Product


class Command(BaseCommand):
    help = (
        "Audita un XLSX de catalogo y lo compara con la DB actual para preparar "
        "una reconstruccion controlada del catalogo."
    )

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", help="Ruta al archivo XLSX a auditar.")
        parser.add_argument(
            "--sample",
            type=int,
            default=20,
            help="Cantidad maxima de filas o grupos a mostrar por seccion.",
        )

    def handle(self, *args, **options):
        xlsx_path = Path(options["xlsx_path"]).expanduser()
        sample = max(1, int(options.get("sample") or 20))

        if not xlsx_path.is_file():
            raise CommandError(f"No existe el archivo: {xlsx_path}")

        workbook_data = self._read_workbook(xlsx_path)
        referenced_ids = workbook_data["referenced_ids"]

        self.stdout.write(self.style.SUCCESS(f"Archivo auditado: {xlsx_path}"))
        self.stdout.write(f"- filas utiles: {workbook_data['row_count']}")
        self.stdout.write(f"- filas con IDProduct: {len(referenced_ids)}")
        self.stdout.write(f"- filas sin IDProduct: {workbook_data['rows_without_idproduct']}")
        self.stdout.write(
            f"- grupos duplicados en XLSX por Nombre + Categorias: {len(workbook_data['duplicate_name_category'])}"
        )
        self.stdout.write(
            f"- IDs duplicados en XLSX: {len(workbook_data['duplicate_idproducts'])}"
        )

        if workbook_data["duplicate_name_category"]:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Duplicados detectados en el XLSX por Nombre + Categorias:"))
            for (name, category_path), total in workbook_data["duplicate_name_category"][:sample]:
                self.stdout.write(f"  - {total} | {name} | {category_path}")

        if workbook_data["duplicate_idproducts"]:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("IDProduct duplicados dentro del XLSX:"))
            for product_id, total in workbook_data["duplicate_idproducts"][:sample]:
                self.stdout.write(f"  - {total} | IDProduct={product_id}")

        db_total = Product.objects.count()
        db_referenced = Product.objects.filter(pk__in=referenced_ids).count() if referenced_ids else 0
        missing_db_ids = sorted(referenced_ids - set(Product.objects.filter(pk__in=referenced_ids).values_list("pk", flat=True)))
        db_only_qs = Product.objects.exclude(pk__in=referenced_ids) if referenced_ids else Product.objects.all()
        db_only_total = db_only_qs.count()
        db_only_with_orders = db_only_qs.filter(order_items__isnull=False).distinct().count()
        db_only_without_orders = db_only_total - db_only_with_orders
        db_name_category_dupes = (
            Product.objects.values("nombre", "categoria_id", "categoria__nombre")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .order_by("-total", "nombre")
        )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Comparacion contra la DB actual"))
        self.stdout.write(f"- productos en DB: {db_total}")
        self.stdout.write(f"- productos de DB referenciados por IDProduct en el XLSX: {db_referenced}")
        self.stdout.write(f"- productos presentes en DB pero no referenciados por el XLSX: {db_only_total}")
        self.stdout.write(f"  - sin pedidos asociados: {db_only_without_orders}")
        self.stdout.write(f"  - con pedidos asociados: {db_only_with_orders}")
        self.stdout.write(f"- IDs presentes en el XLSX pero ausentes en DB: {len(missing_db_ids)}")
        self.stdout.write(f"- grupos duplicados actuales en DB por Nombre + categoria: {db_name_category_dupes.count()}")

        if missing_db_ids:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Primeros IDs del XLSX que hoy no existen en DB:"))
            for product_id in missing_db_ids[:sample]:
                self.stdout.write(f"  - {product_id}")

        if db_only_total:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Primeros productos de DB no referenciados por el XLSX:"))
            for product in db_only_qs.order_by("id")[:sample]:
                category_name = product.categoria.nombre if product.categoria_id else "Sin categoria"
                has_orders = product.order_items.exists()
                self.stdout.write(
                    f"  - {product.id} | {product.nombre} | categoria={category_name} | "
                    f"activo={product.activo} | pedidos={'si' if has_orders else 'no'}"
                )

        if db_name_category_dupes.exists():
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Primeros duplicados actuales en DB por Nombre + categoria:"))
            for row in db_name_category_dupes[:sample]:
                self.stdout.write(
                    f"  - {row['total']} | {row['nombre']} | categoria={row['categoria__nombre']} | categoria_id={row['categoria_id']}"
                )

    def _read_workbook(self, xlsx_path):
        workbook = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)
        headers = [str(cell or "").strip() for cell in next(rows)]
        header_map = {header: index for index, header in enumerate(headers)}

        required = {"Nombre", "Categorías", "IDProduct"}
        missing = required - set(header_map)
        if missing:
            workbook.close()
            raise CommandError(f"El XLSX no tiene las columnas esperadas: {', '.join(sorted(missing))}")

        key_counter = Counter()
        id_counter = Counter()
        referenced_ids = set()
        row_count = 0
        rows_without_idproduct = 0

        for row in rows:
            if not any(value not in (None, "") for value in row):
                continue
            row_count += 1
            name = str(row[header_map["Nombre"]] or "").strip()
            category_path = str(row[header_map["Categorías"]] or "").strip()
            product_id = str(row[header_map["IDProduct"]] or "").strip()

            key_counter[(name, category_path)] += 1
            if product_id:
                id_counter[product_id] += 1
                try:
                    referenced_ids.add(int(float(product_id)))
                except Exception:
                    pass
            else:
                rows_without_idproduct += 1

        workbook.close()

        duplicate_name_category = [
            (key, total) for key, total in key_counter.items() if total > 1
        ]
        duplicate_name_category.sort(key=lambda item: (-item[1], item[0][0], item[0][1]))

        duplicate_idproducts = [
            (product_id, total) for product_id, total in id_counter.items() if total > 1
        ]
        duplicate_idproducts.sort(key=lambda item: (-item[1], item[0]))

        return {
            "row_count": row_count,
            "rows_without_idproduct": rows_without_idproduct,
            "referenced_ids": referenced_ids,
            "duplicate_name_category": duplicate_name_category,
            "duplicate_idproducts": duplicate_idproducts,
        }

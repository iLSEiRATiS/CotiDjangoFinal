import os
import django
import openpyxl
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cotidjango.settings')
django.setup()

from products.models import Product

def update_skus_from_excel(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    print(f"Reading Excel: {file_path}")
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    sheet = wb.active
    rows = sheet.iter_rows(values_only=True)
    headers = next(rows)
    header_map = {h.strip(): i for i, h in enumerate(headers) if h}

    required_cols = ['IDProduct', 'SKU', 'Nombre']
    for col in required_cols:
        if col not in header_map:
            print(f"Error: Required column '{col}' not found in Excel. Found: {list(header_map.keys())}")
            return

    updated_count = 0
    not_found_count = 0
    total_rows = 0

    print("Starting SKU update process...")
    for row in rows:
        total_rows += 1
        id_product = row[header_map['IDProduct']]
        sku = str(row[header_map['SKU']]).strip() if row[header_map['SKU']] is not None else ""
        nombre = str(row[header_map['Nombre']]).strip() if row[header_map['Nombre']] else ""

        product = None
        if id_product:
            try:
                # Handle case where ID might be a float in Excel
                pk = int(float(id_product))
                product = Product.objects.filter(pk=pk).first()
            except (ValueError, TypeError):
                pass
        
        if not product and nombre:
            product = Product.objects.filter(nombre__iexact=nombre).first()

        if product:
            if product.sku != sku:
                product.sku = sku
                product.save()
                updated_count += 1
        else:
            not_found_count += 1
            if not_found_count <= 5:
                print(f"Sample Not Found - XLS ID: {id_product} | Name: {nombre}")

    print(f"\nUpdate Complete!")
    print(f"Total rows processed: {total_rows}")
    print(f"Products updated: {updated_count}")
    print(f"Products not found in DB: {not_found_count}")

if __name__ == "__main__":
    excel_path = r'C:\Users\facun\OneDrive\Escritorio\SKU_FIX\productos_existentes.xlsx'
    update_skus_from_excel(excel_path)

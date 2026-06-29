from orders.models import Order
from cotidjango.api_pdf import build_stock_request_pdf

order = Order.objects.get(id=19)
pdf_bytes = build_stock_request_pdf(order)

with open("/home/facundo/Escritorio/Proyectos/Cotistore/factura_stock_prueba.pdf", "wb") as f:
    f.write(pdf_bytes)
print("factura_stock_prueba.pdf generated successfully.")

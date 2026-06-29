import random
from django.contrib.auth import get_user_model
from products.models import Product
from orders.models import Order, OrderItem
from cotidjango.api_pdf import build_invoice_pdf

User = get_user_model()
admin_user = User.objects.first()

products_with_sku = list(Product.objects.exclude(sku="").exclude(sku__isnull=True))
products_without_sku = list(Product.objects.filter(sku=""))

sample_products = []
if products_with_sku:
    sample_products.extend(random.sample(products_with_sku, min(5, len(products_with_sku))))
if products_without_sku:
    sample_products.extend(random.sample(products_without_sku, min(3, len(products_without_sku))))

if not sample_products:
    sample_products = list(Product.objects.all()[:6])

random.shuffle(sample_products)

if not sample_products:
    print("No products found in DB.")
else:
    order = Order.objects.create(
        user=admin_user,
        nombre="Cliente de Prueba",
        email="prueba@cotistore.local",
        direccion="Calle Falsa 123",
        ciudad="Buenos Aires",
        cp="1000",
        telefono="123456789",
        estado="pendiente",
        envio=0,
        nota="Pedido generado aleatoriamente para probar factura."
    )

    for p in sample_products:
        OrderItem.objects.create(
            order=order,
            product=p,
            cantidad=random.randint(1, 5),
            precio_unitario=p.precio
        )

    # Re-fetch items to use the @property 'subtotal' correctly
    total = sum(item.precio_unitario * item.cantidad for item in order.items.all())
    order.total = total
    order.save()

    print(f"Order created with ID: {order.id}")

    pdf_bytes = build_invoice_pdf(order)
    with open("/home/facundo/Escritorio/Proyectos/Cotistore/factura_prueba.pdf", "wb") as f:
        f.write(pdf_bytes)
    print("factura_prueba.pdf generated successfully.")

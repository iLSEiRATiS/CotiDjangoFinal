# Resumen de Cambios y Guía de Despliegue en VPS (CotiStore Backend)

## 1. Nuevo Rol: Operador (`operator`)
Se implementó un nuevo rol con permisos intermedios en Django Admin pensado para personal de logística/empaque:
* **Precios Ocultos en Productos:** En el catálogo del admin no se muestra la columna `precio`, no es editable (`list_editable`) y se excluye del formulario de edición.
* **Importes Ocultos en Pedidos:** No se muestra el `total` ni el costo de `envio` en la lista de pedidos ni en el formulario. En los productos del pedido (`OrderItemInline`), no se muestran `precio_unitario` ni `subtotal`.
* **Restricción de Facturas/Presupuestos:** Se removió el botón "Descargar" (PDF de factura) de la lista de pedidos para este rol, y si intentan acceder directamente por URL (`/admin/orders/order/<id>/pdf/`), el servidor devuelve `403 Forbidden`.
* **Reportes de Ventas Bloqueados:** Los endpoints de reportes contables (`AdminSalesCalendarView`, `AdminDailySalesView`, `AdminDailySalesPdfView`) responden `403 Forbidden` si el usuario tiene rol `operator`.
* **Permisos Habilitados:** Los botones de **"Rótulo"** y **"Pedir Stock"** siguen 100% operativos y funcionales para el operador.

---

## 2. Guía de Despliegue en VPS (Producción)

Conéctate a tu VPS (`root@srv1552159` o tu IP de servidor) y ejecuta los siguientes comandos exactos:

```bash
cd /root/CotiDjangoFinal/backend
git pull origin main
source .venv/bin/activate
python manage.py migrate
sudo systemctl restart gunicorn
```

> [!TIP]
> Si tu entorno virtual en el VPS tiene otro nombre (por ejemplo `venv` en vez de `.venv`), ajusta la línea 3: `source venv/bin/activate`.

---

## 3. Asignar el Rol Operador a un Usuario
Desde el panel de Django Admin (`/admin/` o tu URL segura `/panel-seguro-2026-Coti-Store/`):
1. Ve a **Usuarios** (`users` -> `CustomUser`).
2. Selecciona o crea el usuario correspondiente.
3. En el campo **Rol**, selecciona **Operador**.
4. Al guardar, Django le otorgará automáticamente acceso al panel (`is_staff = True`) aplicando todas las restricciones de visualización de precios y totales.

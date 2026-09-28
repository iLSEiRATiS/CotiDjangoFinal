# Resumen de Cambios y Guía de Despliegue en VPS (CotiStore Backend)

## Registro de actualización — 2026-09-09

* **Revisión documental:** Se agregaron fechas explícitas para distinguir esta revisión de los cambios anteriores del proyecto.
* **Último cambio previo en este archivo:** El 2026-09-08 a las 10:54 (Argentina), commit `3fddda5`, se ampliaron las instrucciones para asignar el rol Operador desde una acción del listado o desde la ficha del usuario.
* **Alcance de esta actualización:** Solo documentación; no se modificó código de la aplicación ni se verificó el estado del despliegue en producción.

## 1. Actualización de Precios en Tienda desde la Revisión de Pedidos
Dentro de la revisión/edición de cada pedido en Django Admin (`orders` -> `Order`):
* **Nueva casilla `¿Actualizar en tienda?` por producto:** Cada ítem en la tabla de productos del pedido cuenta con una casilla de verificación.
* **Impacto en el catálogo web:** Si se detecta un precio desactualizado en los pedidos que pasan los clientes, el administrador puede corregir el `precio_unitario` y tildar `¿Actualizar en tienda?`. Al hacer clic en **Guardar** (o **Guardar y seguir editando**), el sistema actualiza automáticamente el `precio` real del producto en la base de datos (y su variante en `atributos_precio` si corresponde), impactando inmediatamente en la tienda web.
* **Flexibilidad para precios especiales:** Si la casilla se deja destildada (su estado por defecto), el cambio de precio solo aplicará a ese pedido en particular (útil para descuentos o acuerdos puntuales), sin alterar el catálogo público.
* **Feedback visual:** Al tildar la casilla, la fila del producto se resalta en verde para confirmar visualmente la acción. Al guardar, Django muestra un mensaje de éxito indicando qué productos fueron actualizados en la tienda.
* **Seguridad de roles:** El campo se encuentra protegido y oculto para el rol `operator`.

---

## 2. Rol: Operador (`operator`)
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
Tienes 2 formas muy fáciles desde el panel de Django Admin (`users` -> `CustomUser`):

* **Opción A (Rápida desde el listado):**
  1. En la lista de usuarios, marca la casilla del usuario (o de varios a la vez).
  2. En el desplegable **Acción: ---------**, selecciona **"Asignar rol: Operador"**.
  3. Haz clic en el botón **Ejecutar**.

* **Opción B (Desde la ficha del usuario):**
  1. Haz clic sobre el nombre del usuario para entrar a su edición.
  2. En la sección **Permisos**, en el campo **Rol**, selecciona **Operador**.
  3. Haz clic en **Guardar**. Al guardar, Django le asigna automáticamente `is_staff = True` y acceso al panel con las restricciones aplicadas.

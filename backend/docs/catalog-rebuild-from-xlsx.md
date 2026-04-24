# Catalog Rebuild From XLSX

Guia conservadora para reconstruir el catalogo tomando un `productos_existentes.xlsx` sano como fuente canonica, sin mezclar eso con deploy de frontend ni con limpiezas manuales improvisadas.

## Objetivo

Usar un XLSX validado como verdad del catalogo para:

1. Confirmar que el archivo esta limpio.
2. Medir la diferencia contra la DB productiva.
3. Reimportar el catalogo sano.
4. Desactivar o retirar los sobrantes que no esten en el XLSX.
5. Validar categorias y conteos antes de dar por terminado el proceso.

## Principio operativo

No conviene truncar productos a ciegas en produccion porque `orders.OrderItem.product` usa `PROTECT`.

Por eso el flujo recomendado es:

1. Importar el XLSX canonico sobre la base actual para actualizar o recrear la parte sana.
2. Identificar los productos que quedaron fuera del XLSX.
3. Para esos sobrantes:
   - borrar solo los que no tengan pedidos asociados
   - desactivar los que si tengan pedidos asociados

Este enfoque evita romper historial de pedidos.

## Archivo canonico

Ejemplo validado en este proyecto:

- `C:\Users\facun\OneDrive\Escritorio\final\productos_existentes.xlsx`

Resultado esperado del audit sobre ese archivo:

- filas utiles: `2435`
- duplicados por `Nombre + Categorias`: `0`
- `IDProduct` duplicados: `0`

## Paso 1. Auditar el XLSX localmente

Desde el backend:

```bash
cd /ruta/a/CotiDjangoFinal/backend
source .venv/bin/activate
python manage.py audit_catalog_xlsx "/ruta/al/productos_existentes.xlsx"
```

Si el archivo tiene duplicados internos, hay que corregir primero el XLSX y no seguir.

## Paso 2. Backup de produccion

Antes de tocar datos:

```bash
pg_dump "$DATABASE_URL" > catalog_rebuild_pre_$(date +%F_%H%M%S).sql
```

## Paso 3. Subir el XLSX canonico al VPS

Copiar el archivo a una ruta estable, por ejemplo:

- `/root/catalog_rebuild/productos_existentes.xlsx`

## Paso 4. Auditar el XLSX en el VPS contra la DB productiva

```bash
cd /root/CotiDjangoFinal/backend
source .venv/bin/activate
python manage.py audit_catalog_xlsx /root/catalog_rebuild/productos_existentes.xlsx
```

Puntos a mirar:

1. `productos presentes en DB pero no referenciados por el XLSX`
2. `sin pedidos asociados`
3. `con pedidos asociados`
4. `grupos duplicados actuales en DB por Nombre + categoria`

Este reporte define el alcance real del saneamiento.

## Paso 5. Importar el XLSX canonico

Opcion recomendada:

1. Entrar al admin de productos.
2. Ir a importar XLSX.
3. Subir el `productos_existentes.xlsx` auditado.

Motivo:

- reutiliza el importador ya endurecido del proyecto
- respeta `IDProduct`
- crea categorias faltantes siguiendo la ruta de `Categorías`
- deduplica heuristicas ya cubiertas por tests

## Paso 6. Tratar sobrantes fuera del XLSX

Despues de importar, volver a correr:

```bash
python manage.py audit_catalog_xlsx /root/catalog_rebuild/productos_existentes.xlsx
```

Objetivo del segundo audit:

- bajar a cero o casi cero los productos activos que no esten en el XLSX

Regla recomendada para sobrantes:

1. productos sin pedidos asociados: borrar
2. productos con pedidos asociados: dejar `activo=False`

## Paso 7. Limpiar categorias sobrantes o duplicadas

Si todavia quedan ramas duplicadas:

```bash
python manage.py dedupe_categories
python manage.py dedupe_categories --apply
```

Y si hubiera movimientos ya conocidos:

```bash
python manage.py sanitize_category_moves
python manage.py sanitize_category_moves --apply
```

## Paso 8. Validacion funcional

Chequear:

1. `/api/products?page=1&limit=24`
2. `/api/categories-list`
3. frontend `/productos`
4. conteo visible del catalogo
5. categorias del sidebar
6. 10 productos tomados al azar

## Criterio de cierre

Se considera reconstruccion exitosa cuando:

1. el audit del XLSX da `0` duplicados internos
2. el catalogo visible coincide con el XLSX
3. los productos sobrantes fuera del XLSX estan eliminados o inactivos
4. las categorias visibles ya no arrastran duplicados estructurales

## Lo que no hay que hacer

1. no borrar toda la tabla `products_product` a ciegas
2. no mover categorias manualmente desde SQL
3. no aplicar deduplicaciones masivas sin simulacion previa
4. no mezclar este proceso con cambios de frontend o deploys no relacionados

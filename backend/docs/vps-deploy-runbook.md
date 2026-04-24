# VPS deploy runbook

Guia conservadora para pasar cambios a produccion sin mezclar deploy de codigo con cambios de datos.

## Supuestos

- El backend corre en Linux con `gunicorn`.
- El frontend oficial desplegado sale desde `DjangoFrontCoti`.
- La base productiva usa PostgreSQL via `DATABASE_URL`.
- Los cambios de categorias se aplican con `sanitize_category_moves`, no manualmente desde la base.

## Antes de tocar nada

1. Confirmar que ambos repos ya tienen en `main` lo que queres desplegar.
2. Tener a mano el nombre real del servicio del backend.
3. Tener a mano la ruta real del backend y del frontend en el VPS.
4. Hacer backup de la base de datos.

Ejemplo de backup PostgreSQL:

```bash
pg_dump "$DATABASE_URL" > backup_pre_deploy_$(date +%F_%H%M%S).sql
```

## Backend

Entrar a la carpeta del backend real en el VPS y ejecutar:

```bash
cd /ruta/al/CotiDjangoFinal/backend
git checkout main
git pull origin main
source .venv/bin/activate
python manage.py check
python manage.py showmigrations
python manage.py sanitize_category_moves
```

Si la simulacion muestra exactamente lo esperado, aplicar:

```bash
python manage.py sanitize_category_moves --apply
python manage.py collectstatic --noinput
sudo systemctl restart <nombre-del-servicio-backend>
```

## Frontend

Entrar a la carpeta del frontend oficial desplegado y ejecutar:

```bash
cd /ruta/al/DjangoFrontCoti
git checkout main
git pull origin main
npm install
npm run build
```

Si el frontend se sirve desde Nginx o desde un directorio publico, copiar o publicar el contenido de `dist/` segun tu configuracion actual.

## Validacion post deploy

Chequear manualmente:

1. `https://tu-dominio/admin/`
2. `https://tu-dominio/admin/products/product/importar-xlsx/`
3. `https://tu-dominio/api/categories-list`
4. login desde el frontend
5. catalogo `/productos`
6. exportacion XLSX
7. importacion XLSX
8. categorias `Bengalas` y `Articulos Para Manualidades`

## Si algo sale mal

1. No seguir aplicando cambios manuales.
2. Restaurar el backup de base si el problema fue de datos.
3. Volver a desplegar el commit anterior si el problema fue de codigo.
4. Repetir `sanitize_category_moves` solo despues de entender el estado real del servidor.

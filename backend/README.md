# Coti Store 2.0 (Django API + React SPA)

Backend en Django/DRF que expone las rutas esperadas por el frontend React (login, catalogo, cuentas, pedidos y admin).

## Fuente oficial actual
- Backend oficial: este directorio `backend/`
- Frontend oficial que consume esta API: `..\..\DjangoFrontCoti`
- La carpeta `..\frontend` dentro de `CotiDjangoFinal` queda como SPA legacy/alternativa y no se toma como fuente principal de trabajo por ahora.

## Stack
- Django 5 + DRF + SimpleJWT
- SQLite por defecto con soporte para PostgreSQL via `DATABASE_URL`
- Bootstrap 5 para vistas server-side
- WhiteNoise para estaticos
- React 18 + Vite en `DjangoFrontCoti`

## Backend: configurar y correr
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

- Crear admin: `python manage.py createsuperuser`
- Admin: `http://localhost:8000/admin/`
- Tienda SSR: `http://localhost:8000/`
- API salud: `http://localhost:8000/api/health/`

## Frontend oficial
```bash
cd ..\..\DjangoFrontCoti
npm install
npm run dev -- --host 127.0.0.1 --port 4173
```

## Rutas REST consumidas por React
- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET /api/products`, `GET /api/products/<id-o-slug>`
- `PATCH/GET /api/account/profile`, `PATCH /api/account/password`
- `POST /api/orders`, `GET /api/orders/mine`, `GET /api/orders/<id>`, `PATCH /api/orders/<id>/pay`
- `GET /api/offers`
- Admin: `/api/admin/overview|users|orders|products|offers|upload-image`

## Runbook VPS
Para pasar cambios a produccion sin mezclar codigo y datos:

1. Hacer backup de la base de datos antes de tocar nada.
2. Actualizar el backend a `main`.
3. Activar el entorno virtual del servidor.
4. Correr chequeos basicos de Django.
5. Ejecutar `sanitize_category_moves` primero en simulacion.
6. Si el resultado coincide con lo esperado, ejecutar `sanitize_category_moves --apply`.
7. Recolectar estaticos y reiniciar los servicios necesarios.
8. Validar admin, login, catalogo y flujo XLSX.

Comandos orientativos:

```bash
git checkout main
git pull origin main
source .venv/bin/activate
python manage.py check
python manage.py showmigrations
python manage.py sanitize_category_moves
python manage.py sanitize_category_moves --apply
python manage.py collectstatic --noinput
```

Chequeos recomendados despues del deploy:
- `/admin/`
- `/admin/products/product/importar-xlsx/`
- `/api/categories-list`
- login desde el frontend oficial
- catalogo `/productos`

## Notas
- Se anadio un importador `import_frontend_products` para cargar productos demo desde JSON.
- El campo `avatar` en usuarios permite subir imagenes desde la SPA.
- Para migrar de SQLite a PostgreSQL sin romper datos, ver `docs/postgresql-migration.md`.
- Para deploys en VPS con cambios de codigo + saneo de categorias, ver `docs/vps-deploy-runbook.md`.

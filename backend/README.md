# Coti Store 2.0 (Django API + React SPA)

Backend en Django/DRF que expone las rutas esperadas por el frontend React (login, catalogo, cuentas, pedidos y admin). Se mantiene la UI server-side con Bootstrap, pero podes usar la SPA en `Frontend/` apuntando al API de Django.

## Stack
- Django 5 + DRF + SimpleJWT (tokens `Bearer ...`)
- SQLite por defecto (puede apuntarse a cualquier SQL)
- Bootstrap 5 para vistas server-side
- WhiteNoise para estaticos
- React 18 (Create React App) en `/Frontend` consumiendo `/api/...` del backend

## Backend: configurar y correr
```
cd cotidjango
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
# opcional: poblar productos demo desde Frontend/src/data/productos.json
python manage.py import_frontend_products --limit 120
python manage.py runserver 0.0.0.0:8000
```
- Crear admin: `python manage.py createsuperuser`
- Admin: `http://localhost:8000/admin/`
- Tienda SSR: `http://localhost:8000/`
- API salud: `http://localhost:8000/api/health/`

### Rutas REST consumidas por React
- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET /api/products`, `GET /api/products/<id-o-slug>` (precio solo para usuarios logueados)
- `PATCH/GET /api/account/profile`, `PATCH /api/account/password`
- `POST /api/orders`, `GET /api/orders/mine`, `GET /api/orders/<id>`
- Admin: `/api/admin/overview|users|orders|products|upload-image` (solo staff)

## Frontend (React SPA)
```
cd Frontend
npm install
# el .env ya apunta al API local en http://localhost:8000
npm start
```

## Notas
- Se anadio un importador `import_frontend_products` que lee el JSON de la SPA y carga categorias/productos en Django.
- El campo `avatar` en usuarios permite subir imagenes desde la SPA (se guarda en `/media/avatars/`).

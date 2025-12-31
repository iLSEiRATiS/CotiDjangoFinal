# Coti_NodeDjango

Arquitectura: backend Django/DRF (API), frontend React + Vite, microservicio Node opcional (Express + WebSocket), DB PostgreSQL/SQLite.

## Estructura
- `backend/`: copia del backend Django (api_bridge incluido) listo para API REST.
- `frontend/`: React + Vite con el mismo look & feel del Frontend original (categorías, cards, textos, colores).
- `microservice/`: stub Express + WebSocket para tareas rápidas/notificaciones.

## Backend (Django)
```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```
- Salud: `http://localhost:8000/api/health/`
- Admin: `http://localhost:8000/admin/`

## Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173 (apunta al API en http://localhost:8000)
```
Variables en `.env.local` (ya creado): `VITE_API_URL`, `VITE_GOOGLE_CLIENT_ID`, `PLACEHOLDER_HOST`, `PRODUCTS_PER_LEAF`.

## Microservicio Node (Express + WebSocket)
```bash
cd microservice
npm install
npm run dev   # puerto 4001 por defecto, /health y WS de broadcast
```

## Comunicación
- API REST: Django (`/api/...`).
- WebSockets: microservice (`ws://localhost:4001`).
- DB: SQLite por defecto; ajustar `backend/cotidjango/settings.py` para PostgreSQL.

## Notas
- El frontend conserva categorías, cards, textos y estilos del proyecto original (se copió `src/` y `public/`).
- El backend sigue incluyendo el `api_bridge` que mapea las rutas que consume la SPA.
- Puedes borrar la carpeta `C:\Users\facun\OneDrive\Escritorio\Coti_NodeDjango` (fuera de CotiDJRC) si no la usas; la activa está en `CotiDJRC/Coti_NodeDjango`.



.ENV local de Frontend

VITE_API_URL=http://localhost:8000
PLACEHOLDER_HOST=https://placehold.co
PRODUCTS_PER_LEAF=6


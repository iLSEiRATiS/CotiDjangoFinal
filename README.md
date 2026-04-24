# Coti_NodeDjango

Arquitectura: backend Django/DRF (API), frontend React + Vite, microservicio Node opcional (Express + WebSocket), DB PostgreSQL/SQLite.

## Estado actual
- Frontend oficial en uso: `..\DjangoFrontCoti`
- Backend oficial en uso: `backend/`
- `frontend/` dentro de este repo se conserva como copia legacy/alternativa. No se usa como fuente principal para cambios ni deploy por ahora.

## Estructura
- `backend/`: backend Django listo para API REST y admin.
- `frontend/`: SPA React + Vite legacy/alternativa conservada para referencia.
- `microservice/`: stub Express + WebSocket para tareas rapidas/notificaciones.

## Backend (Django)
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

- Salud: `http://localhost:8000/api/health/`
- Admin: `http://localhost:8000/admin/`

## Frontend oficial actual (`..\DjangoFrontCoti`)
```bash
cd ..\DjangoFrontCoti
npm install
npm run dev -- --host 127.0.0.1 --port 4173
```

Variables clave:
- `VITE_API_URL`
- `VITE_GOOGLE_CLIENT_ID`
- `PLACEHOLDER_HOST`
- `PRODUCTS_PER_LEAF`

## Frontend legacy (`frontend/`)
Se conserva por compatibilidad y referencia historica. No se recomienda usarlo como base principal de trabajo mientras `DjangoFrontCoti` siga siendo la SPA oficial.

## Microservicio Node (Express + WebSocket)
```bash
cd microservice
npm install
npm run dev
```

## Comunicacion
- API REST: Django (`/api/...`)
- WebSockets: microservice (`ws://localhost:4001`)
- DB: SQLite por defecto o PostgreSQL via `DATABASE_URL`

## Notas
- El backend sigue incluyendo el `api_bridge` que mapea las rutas que consume la SPA.
- La carpeta `frontend/` no se borra por ahora para evitar romper referencias historicas o futuras comparaciones.

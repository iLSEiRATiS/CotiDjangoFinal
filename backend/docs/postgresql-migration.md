# Migracion segura de SQLite a PostgreSQL

Esta guia deja el proyecto listo para migrar sin cambiar la logica de la app ni el diseno de modelos.

## 1. Estado actual

- SQLite sigue siendo el fallback local.
- PostgreSQL se activa solo si `DATABASE_URL` esta configurada.
- El driver ya esta incluido en `requirements.txt`: `psycopg[binary]`.

## 2. Preparar PostgreSQL

Crear una base vacia. Ejemplo local:

```sql
CREATE DATABASE cotistore;
```

Definir variables de entorno:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cotistore
DATABASE_CONN_MAX_AGE=600
DATABASE_SSL_REQUIRE=0
```

En produccion, usar `DATABASE_SSL_REQUIRE=1` si el proveedor exige SSL.

## 3. Backup antes de migrar

Desde `backend/`:

```powershell
Copy-Item .\db.sqlite3 .\db.sqlite3.pre_postgres_migration.bak
```

Exportar datos de SQLite a JSON:

```powershell
.\.venv\Scripts\python.exe manage.py dumpdata ^
  --exclude auth.permission ^
  --exclude contenttypes ^
  --indent 2 > data_migration.json
```

Notas:

- Se excluyen `auth.permission` y `contenttypes` para evitar conflictos al recrearlos en PostgreSQL.
- Si no te interesa conservar logs del admin, tambien podes excluir `admin.logentry`.

## 4. Crear esquema en PostgreSQL

Con `DATABASE_URL` ya apuntando a PostgreSQL:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

Validar conexion:

```powershell
.\.venv\Scripts\python.exe manage.py check
```

## 5. Cargar datos

```powershell
.\.venv\Scripts\python.exe manage.py loaddata data_migration.json
```

## 6. Verificaciones obligatorias

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py showmigrations
```

Validaciones manuales:

- login de usuario comun y admin,
- listado de productos,
- detalle con variantes por talle,
- carrito y creacion de pedidos,
- panel admin,
- importacion XLSX,
- carga de imagenes y media.

## 7. Rollback

Si algo falla:

1. quitar `DATABASE_URL`,
2. volver a usar SQLite,
3. restaurar `db.sqlite3.pre_postgres_migration.bak` si hiciste cambios sobre la base local.

## 8. Recomendacion profesional

No cambiar directamente la base de produccion sin una prueba previa.

Orden recomendado:

1. probar PostgreSQL en local,
2. probar en un entorno staging,
3. migrar produccion con backup confirmado,
4. validar flujos criticos,
5. dejar SQLite solo como respaldo historico, no como base activa.

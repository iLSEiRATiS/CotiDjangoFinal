"""
run_local.py – Arranca Django localmente con SQLite.
Uso: python run_local.py
"""
import os
import sys

# Establecer variables ANTES de que settings.py las lea del .env
# (settings.py tiene: if k not in os.environ → no pisa las que ya están)
os.environ["DATABASE_URL"] = ""                     # forzar SQLite local
os.environ["DEBUG"] = "True"
os.environ["ALLOWED_HOSTS"] = "localhost,127.0.0.1"
os.environ["CORS_ALLOWED_ORIGINS"] = "http://localhost:5173,http://localhost:8000"
os.environ["CSRF_TRUSTED_ORIGINS"] = "http://localhost:5173,http://localhost:8000"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cotidjango.settings")

# Construir argv para manage.py
argv = ["manage.py", "runserver", "8000", "--noreload"]
argv += sys.argv[1:]   # permitir pasar args extra

from django.core.management import execute_from_command_line
execute_from_command_line(argv)

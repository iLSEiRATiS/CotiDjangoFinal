from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ("user", "Usuario"),
        ("admin", "Administrador"),
    )
    APPROVAL_CHOICES = (
        ("pending", "Pendiente"),
        ("approved", "Aprobado"),
        ("rejected", "Rechazado"),
    )
    name = models.CharField("nombre", max_length=150, blank=True, default="")
    phone = models.CharField("telefono", max_length=50, blank=True, default="")
    address = models.CharField("direccion", max_length=255, blank=True, default="")
    city = models.CharField("ciudad", max_length=120, blank=True, default="")
    zip_code = models.CharField("codigo postal", max_length=20, blank=True, default="")
    avatar = models.ImageField("avatar", upload_to="avatars/", blank=True, null=True)
    role = models.CharField("rol", max_length=10, choices=ROLE_CHOICES, default="user")
    approval_status = models.CharField("estado de aprobacion", max_length=10, choices=APPROVAL_CHOICES, default="pending")
    welcome_email_sent_at = models.DateTimeField("bienvenida enviada el", null=True, blank=True)
    last_password_changed_at = models.DateTimeField("ultima clave cambiada el", null=True, blank=True)
    groups = models.ManyToManyField(
        "auth.Group",
        related_name="customuser_set",
        blank=True,
        help_text="Grupos de permisos heredados."
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="customuser_set",
        blank=True,
        help_text="Permisos específicos para el usuario."
    )

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def get_full_name_parts(self):
        first = str(self.first_name or "").strip()
        last = str(self.last_name or "").strip()
        return first, last

    def get_display_name(self):
        first, last = self.get_full_name_parts()
        full = " ".join(part for part in [first, last] if part).strip()
        if full:
            return full
        return str(self.name or self.username or self.email or "user").strip()

    def get_missing_profile_fields(self):
        missing = []
        if not str(self.first_name or "").strip():
            missing.append("first_name")
        if not str(self.last_name or "").strip():
            missing.append("last_name")
        return missing

    def _should_be_admin(self):
        return self.is_superuser or self.is_staff or self.role == "admin"

    def _sync_access_flags(self):
        if self._should_be_admin():
            self.role = "admin"
            self.approval_status = "approved"
            self.is_active = True
            return
        self.is_active = self.approval_status == "approved"

    def set_approval_status(self, status):
        self.approval_status = status
        self._sync_access_flags()

    def save(self, *args, **kwargs):
        self._sync_access_flags()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.username or self.email or "user"


class PasswordResetToken(models.Model):
    user = models.ForeignKey(CustomUser, verbose_name="usuario", on_delete=models.CASCADE, related_name="password_reset_tokens")
    token_hash = models.CharField("hash del token", max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField("vence el")
    used_at = models.DateTimeField("usado el", null=True, blank=True)
    created_at = models.DateTimeField("creado el", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Token de restablecimiento"
        verbose_name_plural = "Tokens de restablecimiento"

    @property
    def is_active(self):
        return self.used_at is None and self.expires_at > timezone.now()

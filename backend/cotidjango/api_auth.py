from datetime import timedelta
import secrets

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import PasswordResetToken
from .api_common import User, _reset_token_hash, build_token, send_password_reset_email, serialize_user


def _normalize_email(value):
    return str(value or "").strip().lower()


def _user_exists_for_email(email, exclude_pk=None):
    queryset = User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email))
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset.exists()


def _find_auth_candidate(identifier):
    if "@" in identifier:
        candidate = User.objects.filter(email__iexact=identifier).first()
        if candidate:
            return candidate
    return User.objects.filter(username__iexact=identifier).first()


class AuthRegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        email = _normalize_email(request.data.get("email"))
        password = (request.data.get("password") or "").strip()
        if not name or not email or not password:
            return Response({"error": "Faltan campos"}, status=status.HTTP_400_BAD_REQUEST)
        if _user_exists_for_email(email):
            return Response({"error": "Email ya registrado"}, status=status.HTTP_409_CONFLICT)
        username = email or slugify(name) or f"user-{timezone.now().timestamp()}"
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            name=name,
            approval_status="pending",
            is_active=False,
        )
        return Response(
            {
                "pending": True,
                "detail": "Cuenta creada. Un administrador debe aprobar tu registro antes de ingresar.",
                "user": serialize_user(user, request),
            },
            status=status.HTTP_201_CREATED,
        )


class AuthLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = (request.data.get("email") or request.data.get("username") or "").strip()
        password = (request.data.get("password") or "").strip()
        if not email or not password:
            return Response({"error": "Email y contrasena son requeridos"}, status=status.HTTP_400_BAD_REQUEST)

        candidate = _find_auth_candidate(email)

        user = authenticate(request, username=email, password=password)
        if not user and "@" in email and candidate:
            user = authenticate(request, username=candidate.username, password=password)
        if candidate and candidate.check_password(password):
            if candidate.approval_status == "pending":
                return Response({"error": "Tu cuenta esta pendiente de aprobacion por un administrador."}, status=status.HTTP_403_FORBIDDEN)
            if candidate.approval_status == "rejected":
                return Response({"error": "Tu registro fue rechazado. Contacta al administrador para mas informacion."}, status=status.HTTP_403_FORBIDDEN)
        if not user:
            return Response({"error": "Credenciales invalidas"}, status=status.HTTP_401_UNAUTHORIZED)

        token = build_token(user)
        return Response({"token": token, "user": serialize_user(user, request)})


class AuthMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"user": serialize_user(request.user, request)})


class AuthForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = _normalize_email(request.data.get("email"))
        generic_ok = {"ok": True, "detail": "Si el email existe, enviamos instrucciones para restablecer la contrasena."}
        if not email:
            return Response(generic_ok)
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response(generic_ok)
        raw_token = secrets.token_urlsafe(32)
        token_hash = _reset_token_hash(raw_token)
        expires_at = timezone.now() + timedelta(minutes=30)
        PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        PasswordResetToken.objects.create(user=user, token_hash=token_hash, expires_at=expires_at)
        mail_result = send_password_reset_email(user, raw_token) or {}
        if not mail_result.get("sent") and settings.DEBUG:
            return Response({
                **generic_ok,
                "debug": {
                    "resetLink": mail_result.get("reset_link"),
                    "mailError": mail_result.get("error") or "mail-not-sent",
                },
            })
        return Response(generic_ok)


class AuthResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        raw_token = str(request.data.get("token") or "").strip()
        new_password = str(request.data.get("newPassword") or request.data.get("new_password") or "").strip()
        if not raw_token or not new_password:
            return Response({"error": "Token y nueva contrasena son requeridos"}, status=status.HTTP_400_BAD_REQUEST)
        token_hash = _reset_token_hash(raw_token)
        row = PasswordResetToken.objects.select_related("user").filter(token_hash=token_hash, used_at__isnull=True).first()
        if not row or row.expires_at <= timezone.now():
            return Response({"error": "Enlace invalido o expirado"}, status=status.HTTP_400_BAD_REQUEST)
        user = row.user
        try:
            validate_password(new_password, user=user)
        except ValidationError as exc:
            return Response({"error": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save(update_fields=["password"])
        row.used_at = timezone.now()
        row.save(update_fields=["used_at"])
        return Response({"ok": True, "detail": "Contrasena actualizada correctamente"})


class AccountProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        return Response({"user": serialize_user(request.user, request)})

    def patch(self, request):
        user = request.user
        name = request.data.get("name")
        email = request.data.get("email")
        profile = request.data.get("profile") if isinstance(request.data.get("profile"), dict) else {}
        shipping = request.data.get("shipping") if isinstance(request.data.get("shipping"), dict) else {}
        profile_phone = request.data.get("profilePhone")
        remove_avatar = str(request.data.get("removeAvatar") or "").lower() in {"1", "true", "yes"}
        avatar_file = request.FILES.get("avatar")

        if email:
            normalized_email = _normalize_email(email)
            if _user_exists_for_email(normalized_email, exclude_pk=user.pk):
                return Response({"error": "Email ya registrado"}, status=status.HTTP_409_CONFLICT)
            user.email = normalized_email
            user.username = user.username or normalized_email

        if name is not None:
            user.name = name

        phone_val = profile.get("phone") if profile else None
        if profile_phone is not None:
            phone_val = profile_phone
        if phone_val is not None:
            user.phone = phone_val

        if shipping:
            if "name" in shipping:
                user.name = shipping.get("name") or user.name
            if "address" in shipping:
                user.address = shipping.get("address") or ""
            if "city" in shipping:
                user.city = shipping.get("city") or ""
            if "zip" in shipping:
                user.zip_code = shipping.get("zip") or ""
            if "phone" in shipping:
                user.phone = shipping.get("phone") or user.phone

        if remove_avatar and user.avatar:
            user.avatar.delete(save=False)
            user.avatar = None
        if avatar_file:
            user.avatar = avatar_file

        user.save()
        return Response({"user": serialize_user(user, request)})


class AccountPasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        current = request.data.get("currentPassword") or request.data.get("old_password")
        new = request.data.get("newPassword") or request.data.get("new_password")
        if not current or not new:
            return Response({"error": "Faltan campos"}, status=status.HTTP_400_BAD_REQUEST)
        if not request.user.check_password(current):
            return Response({"error": "Contrasena actual incorrecta"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(new, user=request.user)
        except ValidationError as exc:
            return Response({"error": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        request.user.set_password(new)
        request.user.save()
        return Response({"detail": "Contrasena actualizada"})

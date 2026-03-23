from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import HomeImage, HomeMarquee, SupplierContact
from .api_common import _verify_turnstile, serialize_home_image, serialize_home_marquee


class HomeImagesView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        qs = HomeImage.objects.filter(activo=True).order_by("section", "order", "id")
        items = [serialize_home_image(x) for x in qs]
        by_key_image = {x["key"]: x["imageUrl"] for x in items}
        by_key_target = {x["key"]: x["targetUrl"] for x in items if x.get("targetUrl")}
        marquee = HomeMarquee.objects.order_by("-id").first()
        return Response({
            "items": items,
            "byKey": by_key_image,
            "byKeyTarget": by_key_target,
            "marquee": serialize_home_marquee(marquee),
        })


class SupplierContactCreateView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        nombre = str(request.data.get("nombre") or "").strip()
        apellido = str(request.data.get("apellido") or "").strip()
        telefono = str(request.data.get("telefono") or "").strip()
        mensaje = str(request.data.get("mensaje") or "").strip()
        turnstile_token = str(request.data.get("turnstileToken") or "").strip()
        archivo = request.FILES.get("archivo")

        if not nombre or not apellido or not telefono or not mensaje:
            return Response({"detail": "Completa todos los campos obligatorios."}, status=status.HTTP_400_BAD_REQUEST)
        if not _verify_turnstile(turnstile_token, request.META.get("REMOTE_ADDR", "")):
            return Response({"detail": "Captcha invalido. Intenta nuevamente."}, status=status.HTTP_400_BAD_REQUEST)

        if archivo:
            ext = Path(archivo.name or "").suffix.lower()
            allowed_exts = {".pdf", ".doc", ".docx"}
            allowed_types = {
                "application/pdf",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            }
            if ext not in allowed_exts and getattr(archivo, "content_type", "") not in allowed_types:
                return Response({"detail": "El archivo debe ser PDF, DOC o DOCX."}, status=status.HTTP_400_BAD_REQUEST)
            if getattr(archivo, "size", 0) > 5 * 1024 * 1024:
                return Response({"detail": "El archivo no puede superar los 5 MB."}, status=status.HTTP_400_BAD_REQUEST)

        contact = SupplierContact.objects.create(
            nombre=nombre,
            apellido=apellido,
            telefono=telefono,
            mensaje=mensaje,
            archivo=archivo,
        )
        mail_sent = False
        recipients = list(getattr(settings, "ADMIN_NOTIFICATION_EMAILS", []) or [])
        if recipients:
            body = "\n".join([
                "Nuevo contacto comercial recibido desde el formulario web.",
                "",
                f"Nombre: {nombre} {apellido}",
                f"Telefono: {telefono}",
                "",
                "Mensaje:",
                mensaje,
            ])
            email = EmailMessage(
                subject=f"Nuevo contacto comercial - {nombre} {apellido}",
                body=body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "") or None,
                to=recipients,
            )
            if archivo:
                try:
                    archivo.seek(0)
                except Exception:
                    pass
                try:
                    email.attach(archivo.name, archivo.read(), getattr(archivo, "content_type", "application/octet-stream"))
                except Exception:
                    pass
            try:
                email.send(fail_silently=False)
                mail_sent = True
            except Exception:
                mail_sent = False
        return Response({"id": contact.id, "message": "Contacto recibido correctamente.", "mailSent": mail_sent}, status=status.HTTP_201_CREATED)

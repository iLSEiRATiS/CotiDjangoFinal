import base64
import json
import os
from urllib import error as urlerror
from urllib import request as urlrequest

from django.conf import settings
from django.core.mail import EmailMessage

from .api_order_utils import order_item_attrs_label, order_item_name
from .api_pdf import build_invoice_pdf


def _normalize_resend_attachments(attachments=None):
    items = []
    for attachment in attachments or []:
        if not isinstance(attachment, dict):
            continue
        filename = str(attachment.get("filename") or "").strip()
        content = attachment.get("content")
        content_type = str(attachment.get("content_type") or attachment.get("contentType") or "").strip()
        if not filename or content in (None, ""):
            continue
        if isinstance(content, bytes):
            encoded = base64.b64encode(content).decode("ascii")
        else:
            encoded = str(content).strip()
        if not encoded:
            continue
        item = {
            "filename": filename,
            "content": encoded,
        }
        if content_type:
            item["content_type"] = content_type
        items.append(item)
    return items


def send_resend_email(to_emails, subject, text_body, html_body=None, reply_to=None, attachments=None):
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("RESEND_FROM_EMAIL", "").strip() or "onboarding@resend.dev"
    if not api_key or not to_emails:
        return {"sent": False, "error": "missing-api-key-or-recipient"}
    payload = {
        "from": from_email,
        "to": to_emails,
        "subject": subject or "",
    }
    if text_body:
        payload["text"] = text_body
    if html_body:
        payload["html"] = html_body
    if reply_to:
        payload["reply_to"] = [str(reply_to).strip()]
    normalized_attachments = _normalize_resend_attachments(attachments)
    if normalized_attachments:
        payload["attachments"] = normalized_attachments
    try:
        req = urlrequest.Request(
            "https://api.resend.com/emails",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "cotistore-backend/1.0",
            },
            method="POST",
        )
        with urlrequest.urlopen(req, timeout=15) as resp:
            status_code = getattr(resp, "status", 0) or 0
            body = resp.read().decode("utf-8", errors="replace")
            return {
                "sent": 200 <= status_code < 300,
                "status_code": status_code,
                "body": body,
            }
    except urlerror.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return {
            "sent": False,
            "status_code": getattr(exc, "code", None),
            "error": body or repr(exc),
        }
    except Exception as exc:
        return {"sent": False, "error": repr(exc)}


def send_invoice_email(order, request=None):
    if not order.email:
        return
    pdf_bytes = build_invoice_pdf(order)
    subject = f"Presupuesto de tu pedido #{order.id}"
    body = (
        f"Hola {order.nombre},\n\n"
        f"Adjuntamos el presupuesto de tu pedido #{order.id}.\n"
        f"Total: ${order.total}\n"
        f"Estado: {order.status}\n\n"
        "Gracias por tu compra."
    )
    reply_to = os.getenv("RESEND_REPLY_TO")
    html_body = body.replace("\n", "<br>")
    resend_result = send_resend_email(
        [order.email],
        subject,
        body,
        html_body=html_body,
        reply_to=reply_to,
        attachments=[
            {
                "filename": f"pedido-{order.id}.pdf",
                "content": pdf_bytes,
                "content_type": "application/pdf",
            }
        ],
    ) or {}
    if resend_result.get("sent"):
        return
    email = EmailMessage(subject, body, to=[order.email])
    email.attach(f"pedido-{order.id}.pdf", pdf_bytes, "application/pdf")
    try:
        email.send(fail_silently=True)
    except Exception:
        pass


def send_admin_order_email(order, request=None):
    admin_email = (
        os.getenv("ADMIN_ORDER_EMAIL", "").strip()
        or os.getenv("GMAIL_USER", "").strip()
        or getattr(settings, "DEFAULT_FROM_EMAIL", "")
    )
    if not admin_email:
        return

    subject = f"Nuevo pedido #{order.id} para aprobar"
    lines = [
        f"Pedido #{order.id}",
        f"Cliente: {order.nombre} - {order.email}",
        f"Total: ${order.total}",
        f"Estado: {order.status}",
        "",
        "Items:",
    ]
    for item in order.items.all():
        attrs_label = order_item_attrs_label(item.atributos or {})
        lines.append(
            f"- {order_item_name(item)}{attrs_label} x{item.cantidad} @ ${item.precio_unitario:.2f} = ${item.subtotal:.2f}"
        )
    body = "\n".join(lines)
    html_body = body.replace("\n", "<br>")
    reply_to = os.getenv("RESEND_REPLY_TO")

    resend_result = send_resend_email([admin_email], subject, body, html_body=html_body, reply_to=reply_to) or {}
    if resend_result.get("sent"):
        return

    email = EmailMessage(subject, body, to=[admin_email])
    try:
        email.send(fail_silently=True)
    except Exception:
        pass


def _frontend_base_url():
    return (
        os.getenv("FRONTEND_URL", "").strip()
        or os.getenv("APP_FRONTEND_URL", "").strip()
        or "http://localhost:5173"
    ).rstrip("/")


def send_password_reset_email(user, raw_token):
    if not user or not user.email:
        return {"sent": False, "error": "missing-recipient"}
    frontend = _frontend_base_url()
    reset_link = f"{frontend}/reset-password?token={raw_token}"
    subject = "Recuperar contraseña - CotiStore"
    body = (
        f"Hola {user.name or user.username},\n\n"
        "Recibimos una solicitud para cambiar tu contraseña.\n"
        f"Usá este enlace (válido por 30 minutos):\n{reset_link}\n\n"
        "Si no fuiste vos, podés ignorar este correo."
    )
    html_body = (
        f"<p>Hola {user.name or user.username},</p>"
        "<p>Recibimos una solicitud para cambiar tu contraseña.</p>"
        f"<p><a href=\"{reset_link}\">Cambiar contraseña</a> (válido por 30 minutos)</p>"
        "<p>Si no fuiste vos, podés ignorar este correo.</p>"
    )
    reply_to = os.getenv("RESEND_REPLY_TO")
    resend_result = send_resend_email([user.email], subject, body, html_body=html_body, reply_to=reply_to) or {}
    if resend_result.get("sent"):
        return {"sent": True, "provider": "resend", "reset_link": reset_link}
    email = EmailMessage(subject, body, to=[user.email])
    try:
        email.send(fail_silently=False)
        return {"sent": True, "provider": "smtp", "reset_link": reset_link}
    except Exception as exc:
        return {"sent": False, "error": resend_result.get("error") or str(exc), "reset_link": reset_link}


def send_welcome_email(user):
    if not user or not user.email:
        return {"sent": False, "error": "missing-recipient"}
    frontend = _frontend_base_url()
    login_link = f"{frontend}/login"
    subject = "Bienvenido a CotiStore"
    body = (
        f"Hola {user.name or user.username},\n\n"
        "Tu cuenta fue creada correctamente en CotiStore.\n"
        "Si tu acceso requiere aprobación, te avisaremos cuando quede habilitado.\n\n"
        f"Podés ingresar desde aquí:\n{login_link}\n"
    )
    html_body = (
        f"<p>Hola {user.name or user.username},</p>"
        "<p>Tu cuenta fue creada correctamente en CotiStore.</p>"
        "<p>Si tu acceso requiere aprobación, te avisaremos cuando quede habilitado.</p>"
        f"<p><a href=\"{login_link}\">Ingresar</a></p>"
    )
    reply_to = os.getenv("RESEND_REPLY_TO")
    resend_result = send_resend_email([user.email], subject, body, html_body=html_body, reply_to=reply_to) or {}
    if resend_result.get("sent"):
        return {"sent": True, "provider": "resend"}
    email = EmailMessage(subject, body, to=[user.email])
    try:
        email.send(fail_silently=False)
        return {"sent": True, "provider": "smtp"}
    except Exception as exc:
        return {"sent": False, "error": resend_result.get("error") or str(exc)}


def send_password_changed_email(user):
    if not user or not user.email:
        return {"sent": False, "error": "missing-recipient"}
    frontend = _frontend_base_url()
    login_link = f"{frontend}/login"
    subject = "Tu contraseña fue actualizada"
    body = (
        f"Hola {user.name or user.username},\n\n"
        "Te avisamos que tu contraseña fue cambiada correctamente.\n"
        f"Si fuiste vos, podés volver a ingresar desde:\n{login_link}\n\n"
        "Si no reconoces este cambio, contactanos de inmediato."
    )
    html_body = (
        f"<p>Hola {user.name or user.username},</p>"
        "<p>Te avisamos que tu contraseña fue cambiada correctamente.</p>"
        f"<p><a href=\"{login_link}\">Volver a ingresar</a></p>"
        "<p>Si no reconoces este cambio, contactanos de inmediato.</p>"
    )
    reply_to = os.getenv("RESEND_REPLY_TO")
    resend_result = send_resend_email([user.email], subject, body, html_body=html_body, reply_to=reply_to) or {}
    if resend_result.get("sent"):
        return {"sent": True, "provider": "resend"}
    email = EmailMessage(subject, body, to=[user.email])
    try:
        email.send(fail_silently=False)
        return {"sent": True, "provider": "smtp"}
    except Exception as exc:
        return {"sent": False, "error": resend_result.get("error") or str(exc)}

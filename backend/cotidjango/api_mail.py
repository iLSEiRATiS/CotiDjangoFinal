import json
import os
from urllib import request as urlrequest

from django.conf import settings
from django.core.mail import EmailMessage

from .api_order_utils import order_item_attrs_label, order_item_name
from .api_pdf import build_invoice_pdf


def send_resend_email(to_emails, subject, text_body, html_body=None, reply_to=None):
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("RESEND_FROM_EMAIL", "").strip() or "onboarding@resend.dev"
    if not api_key or not to_emails:
        return False
    payload = {
        "from": from_email,
        "to": to_emails,
        "subject": subject or "",
        "text": text_body or "",
    }
    if html_body:
        payload["html"] = html_body
    if reply_to:
        payload["reply_to"] = reply_to
    try:
        req = urlrequest.Request(
            "https://api.resend.com/emails",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlrequest.urlopen(req, timeout=15) as resp:
            status_code = getattr(resp, "status", 0) or 0
            return 200 <= status_code < 300
    except Exception:
        return False


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
    if send_resend_email([order.email], subject, body, html_body=html_body, reply_to=reply_to):
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

    if send_resend_email([admin_email], subject, body, html_body=html_body, reply_to=reply_to):
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
    subject = "Recuperar contraseÃ±a - CotiStore"
    body = (
        f"Hola {user.name or user.username},\n\n"
        "Recibimos una solicitud para cambiar tu contraseÃ±a.\n"
        f"UsÃ¡ este enlace (vÃ¡lido por 30 minutos):\n{reset_link}\n\n"
        "Si no fuiste vos, podÃ©s ignorar este correo."
    )
    html_body = (
        f"<p>Hola {user.name or user.username},</p>"
        "<p>Recibimos una solicitud para cambiar tu contraseÃ±a.</p>"
        f"<p><a href=\"{reset_link}\">Cambiar contraseÃ±a</a> (vÃ¡lido por 30 minutos)</p>"
        "<p>Si no fuiste vos, podÃ©s ignorar este correo.</p>"
    )
    reply_to = os.getenv("RESEND_REPLY_TO")
    if send_resend_email([user.email], subject, body, html_body=html_body, reply_to=reply_to):
        return {"sent": True, "provider": "resend", "reset_link": reset_link}
    email = EmailMessage(subject, body, to=[user.email])
    try:
        email.send(fail_silently=False)
        return {"sent": True, "provider": "smtp", "reset_link": reset_link}
    except Exception as exc:
        return {"sent": False, "error": str(exc), "reset_link": reset_link}

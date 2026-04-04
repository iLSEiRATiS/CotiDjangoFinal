from django.conf import settings
from django.http import HttpResponseForbidden


class AdminAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        admin_prefix = f"/{getattr(settings, 'ADMIN_PATH_PREFIX', 'admin').strip('/')}/"
        allowed_ips = set(getattr(settings, "ADMIN_ALLOWED_IPS", []) or [])
        if allowed_ips and request.path.startswith(admin_prefix):
            forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
            client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.META.get("REMOTE_ADDR") or "").strip()
            if client_ip not in allowed_ips:
                return HttpResponseForbidden("Admin access denied")
        return self.get_response(request)

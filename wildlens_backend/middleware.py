# mysite/middleware.py
import os
import jwt, logging
from django.http import JsonResponse

log = logging.getLogger("supabase")

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")    # copy from Supabase → Settings → API

class SupabaseAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = None

        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            log.debug("Found Bearer header")

        if not token:
            token = request.session.get("supabase_token")
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
        else:
            token = None
            if token:
                log.debug("Using token from session")

        if not token:
            log.debug("❌ No token in header *or* session")
        else:
            try:
                payload = jwt.decode(
                    token,
                    SUPABASE_JWT_SECRET,
                    algorithms=["HS256"],
                    audience="authenticated",
                )
                request.supabase_user = payload
                log.debug("✅ Token OK – sub=%s  role=%s",
                          payload.get("sub"),
                          payload.get("app_metadata", {}).get("role"))
            except jwt.ExpiredSignatureError:
                log.warning("❌ Token expired")
                return JsonResponse({"error": "Token expired"}, status=401)
            except jwt.InvalidTokenError as e:
                log.warning("❌ Invalid token: %s", e)
                return JsonResponse({"error": "Invalid token"}, status=401)

        return self.get_response(request)
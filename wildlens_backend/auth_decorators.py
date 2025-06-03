# mysite/auth_decorators.py
from functools import wraps
from django.http import JsonResponse
import logging
log = logging.getLogger("supabase")

def supabase_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not hasattr(request, "supabase_user"):
            log.debug("Decorator – no user on request")
            return JsonResponse({"detail": "Not authenticated"}, status=401)

        # Keep UID in session for old code that reads request.session['supabase_uid']
        request.session["supabase_uid"] = request.supabase_user["sub"]
        return view_func(request, *args, **kwargs)
    return _wrapped


def supabase_admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not hasattr(request, "supabase_user"):
            return JsonResponse({"detail": "Not authenticated"}, status=401)

        app_meta = request.supabase_user.get("app_metadata", {}) or {}
        if app_meta.get("role") != "admin":
            return JsonResponse({"detail": "Not authorized"}, status=403)

        request.session["supabase_uid"] = request.supabase_user["sub"]
        return view_func(request, *args, **kwargs)
    return _wrapped

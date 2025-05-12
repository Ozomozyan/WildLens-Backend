# mysite/auth_decorators.py

from django.http import JsonResponse

def supabase_login_required(view_func):
    def wrapper(request, *args, **kwargs):
        # Check if request.supabase_user was set by the middleware
        if not hasattr(request, 'supabase_user'):
            return JsonResponse({"error": "Not authenticated"}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


def supabase_admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'supabase_user'):
            return JsonResponse({"error": "Not authenticated"}, status=401)

        # Check if user is admin, e.g. "role" in JWT claims
        # The claim name depends on how you store roles in Supabase
        # Often it's in `request.supabase_user['role']` or `request.supabase_user['app_metadata']`
        app_metadata = request.supabase_user.get('app_metadata') or {}
        if app_metadata.get('role') != 'admin':
            return JsonResponse({"error": "Not authorized"}, status=403)

        return view_func(request, *args, **kwargs)
    return wrapper

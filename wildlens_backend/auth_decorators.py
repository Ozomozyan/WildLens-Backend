# mysite/auth_decorators.py

from django.http import JsonResponse

def supabase_login_required(view_func):
    def wrapper(request, *args, **kwargs):
        # 1) Make sure the middleware decoded the JWT and set supabase_user
        if not hasattr(request, 'supabase_user'):
            return JsonResponse({"error": "Not authenticated"}, status=401)

        # 2) Pull out the user ID ("sub" claim) and save it to the session
        #    so views (like user_dashboard) can read request.session["supabase_uid"]
        uid = request.supabase_user.get('sub')
        if uid:
            request.session['supabase_uid'] = uid

        return view_func(request, *args, **kwargs)
    return wrapper


def supabase_admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        # Cool, they're logged in?
        if not hasattr(request, 'supabase_user'):
            return JsonResponse({"error": "Not authenticated"}, status=401)

        # Make sure we still have the uid in session for downstream
        uid = request.supabase_user.get('sub')
        if uid:
            request.session['supabase_uid'] = uid

        # 3) Check their role
        app_metadata = request.supabase_user.get('app_metadata') or {}
        if app_metadata.get('role') != 'admin':
            return JsonResponse({"error": "Not authorized"}, status=403)

        return view_func(request, *args, **kwargs)
    return wrapper

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse
from django.shortcuts import redirect
from .models import Profile
from .reeval2 import allowed_routes, crossed_study

class PrivateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.path not in ["/password/", "/logout/"] and not request.path.startswith("/static/"):
            profile, _ = Profile.objects.get_or_create(user=request.user)
            if profile.must_change_password:
                return redirect("password")
        response = self.get_response(request)
        if not request.path.startswith("/static/"):
            response["Cache-Control"] = "no-store, private"
            response["Referrer-Policy"] = "same-origin"
            response["X-Robots-Tag"] = "noindex, nofollow"
            # Django admin needs its own scripts/styles. Study pages have no inline JS.
            if not request.path.startswith("/admin/"):
                response["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
        return response


class CrossedStudyGuard:
    """Default-deny access policy of the crossed design (ReEval-2).

    A route is reachable only if the role's list names it, so a route added later
    stays closed until someone decides otherwise. The first study has no crossed
    Study row and passes straight through.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        study = crossed_study()
        if study is None or request.path.startswith("/static/"):
            return None
        match = request.resolver_match
        name = match.url_name if match and not match.namespaces else None
        if not request.user.is_authenticated:
            return None if name in {"login", "logout"} else redirect_to_login(request.get_full_path())
        if name in allowed_routes(request.user, study):
            return None
        return HttpResponse("Esta sección no está disponible para tu cuenta en este momento del estudio.", status=403)

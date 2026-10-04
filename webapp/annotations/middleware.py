from django.shortcuts import redirect
from .models import Profile

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

from django.shortcuts import redirect, render


def home(request):
    if getattr(request, "tenant", None) is not None:
        from portal.views import home as portal_home
        return portal_home(request)

    if request.user.is_authenticated and getattr(request.user, "tenant_id", None):
        return redirect("portal-login")

    is_staff = request.user.is_authenticated and (
        getattr(request.user, "is_platform_staff", False) or request.user.is_superuser
    )
    return render(request, "home.html", {"is_staff": is_staff})
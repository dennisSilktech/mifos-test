from django.shortcuts import redirect, render

def home(request):
    # 1. Tenant domain request: redirect straight to the portal route
    if getattr(request, "tenant", None) is not None:
        return redirect("portal:home")

    # 2. Main platform domain request: render platform landing page
    is_staff = request.user.is_authenticated and (
        getattr(request.user, "is_platform_staff", False) or request.user.is_superuser
    )
    return render(request, "platform/index.html", {"is_staff": is_staff})
from django.shortcuts import redirect, render


def home(request):
    # 1. Unauthenticated users go straight to login
    if not request.user.is_authenticated:
        return redirect("portal:portal-login")

    # 2. Check if user is platform staff / superuser trying to access root platform
    if request.user.is_superuser or getattr(request.user, "is_platform_staff", False):
        return redirect("dashboard:tenant-list")  # Or your main platform dashboard route

    # 3. Authenticated tenant users get redirected or rendered
    tenant = getattr(request, "tenant", None) or getattr(request.user, "tenant", None)
    
    if not tenant:
        # Fallback if no tenant context exists for logged-in non-staff user
        return redirect("portal:portal-login")

    # Render portal home template if it exists, or redirect to main portal landing
    return render(request, "portal/home.html", {"tenant": tenant})
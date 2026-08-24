import secrets

from django.contrib.auth.hashers import make_password
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .middleware import get_client_ip
from .models import APIKey, LoginSession
from .serializers import APIKeySerializer, LoginSerializer, LoginSessionSerializer, RefreshSerializer
from .services import AuthenticationError, AuthenticationService


class LoginView(APIView):
    permission_classes = []
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant = getattr(request, "tenant", None)
        try:
            tokens = AuthenticationService.authenticate(
                email=serializer.validated_data["email"],
                password=serializer.validated_data["password"],
                mfa_code=serializer.validated_data.get("mfa_code"),
                tenant=tenant,
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                device_fingerprint=request.META.get("HTTP_X_DEVICE_ID", ""),
            )
        except AuthenticationError as exc:
            return Response({"error": {"code": exc.code, "message": exc.message}}, status=401)

        return Response(tokens, status=status.HTTP_200_OK)


class RefreshView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tokens = AuthenticationService.rotate_refresh_token(
                serializer.validated_data["refresh"],
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except AuthenticationError as exc:
            return Response({"error": {"code": exc.code, "message": exc.message}}, status=401)
        return Response(tokens)


class LogoutAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        AuthenticationService.revoke_all_sessions(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MFAEnrollView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        provisioning_uri = AuthenticationService.enroll_mfa(request.user)
        return Response({"provisioning_uri": provisioning_uri})


class MFAConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("code", "")
        if AuthenticationService.confirm_mfa_enrollment(request.user, code):
            return Response({"mfa_enabled": True})
        return Response({"error": {"code": "MFA_INVALID_CODE", "message": "Invalid code."}}, status=400)


class LoginSessionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LoginSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LoginSession.objects.filter(user=self.request.user).order_by("-created_at")


class APIKeyViewSet(viewsets.ModelViewSet):
    serializer_class = APIKeySerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        return APIKey.objects.filter(tenant=tenant) if tenant else APIKey.objects.none()

    def create(self, request, *args, **kwargs):
        raw_key = f"bnk_live_{secrets.token_urlsafe(24)}"
        prefix = raw_key[:12]
        api_key = APIKey.objects.create(
            tenant=request.tenant,
            name=request.data.get("name", "API Key"),
            key_prefix=prefix,
            key_hash=make_password(raw_key),
            scopes=request.data.get("scopes", []),
            created_by=request.user,
        )
        data = APIKeySerializer(api_key).data
        data["raw_key"] = raw_key  # shown once
        return Response(data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)

from rest_framework import serializers

from .models import APIKey, LoginSession, User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    mfa_code = serializers.CharField(required=False, allow_blank=True)


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "email", "phone_number", "first_name", "last_name", "role",
            "tenant", "is_platform_staff", "is_active", "is_email_verified",
            "mfa_enabled", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class LoginSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginSession
        fields = ["id", "ip_address", "user_agent", "device_fingerprint", "is_revoked",
                  "created_at", "expires_at"]


class APIKeySerializer(serializers.ModelSerializer):
    raw_key = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = APIKey
        fields = ["id", "tenant", "name", "key_prefix", "scopes", "is_active",
                  "last_used_at", "expires_at", "created_at", "raw_key"]
        read_only_fields = ["id", "key_prefix", "last_used_at", "created_at"]

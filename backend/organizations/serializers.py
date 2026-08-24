from rest_framework import serializers

from .models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id", "legal_name", "trading_name", "org_type", "registration_number",
            "country", "contact_email", "contact_phone", "kyc_verified",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "kyc_verified", "created_at", "updated_at"]

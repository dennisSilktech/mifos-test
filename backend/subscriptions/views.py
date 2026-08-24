from rest_framework import serializers, viewsets

from authentication.permissions import IsFinanceOrSuperAdmin

from .models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = [
            "id", "tenant", "plan", "status", "max_members", "max_branches",
            "trial_ends_at", "current_period_start", "current_period_end", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.select_related("tenant").all()
    serializer_class = SubscriptionSerializer
    permission_classes = [IsFinanceOrSuperAdmin]
    filterset_fields = ["status", "plan", "tenant"]
    http_method_names = ["get", "post", "patch"]

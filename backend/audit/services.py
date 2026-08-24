from celery import shared_task


class AuditService:
    @staticmethod
    def log(*, actor=None, tenant=None, action, actor_ip=None, target_type="", target_id="", metadata=None):
        from .models import AuditLog

        AuditLog.objects.create(
            actor_user=actor,
            tenant=tenant,
            actor_ip=actor_ip,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata or {},
        )


@shared_task
def log_action_async(*, actor_id=None, tenant_id=None, action, actor_ip=None,
                      target_type="", target_id="", metadata=None):
    from authentication.models import User
    from tenants.models import Tenant

    actor = User.objects.filter(id=actor_id).first() if actor_id else None
    tenant = Tenant.objects.filter(id=tenant_id).first() if tenant_id else None
    AuditService.log(
        actor=actor, tenant=tenant, action=action, actor_ip=actor_ip,
        target_type=target_type, target_id=target_id, metadata=metadata,
    )
